import requests
import base64
import re
import multiprocessing
from utils import (
    handle_main_execution,
    load_sync_config,
    load_organizations,
)
from log import get_logger, setup_logging
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
from tqdm import tqdm

disable_warnings(InsecureRequestWarning)


class APIClient:
    def __init__(self, base_url, **session_kwargs):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        for key, value in session_kwargs.items():
            setattr(self.session, key, value)

    def _request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}{endpoint}"
        try:
            r = self.session.request(method, url, **kwargs)
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {method} {url} - {e}")
            return None


class IQ(APIClient):
    def __init__(self, url, username, password):
        super().__init__(
            url,
            auth=(username, password),
            headers={"Accept": "application/json"},
            verify=False,
        )

    def get_applications(self, org_id):
        r = self._request("GET", f"/api/v2/applications/organization/{org_id}")
        return (
            {a["name"]: a["id"] for a in r.json().get("applications", [])} if r else {}
        )

    def create_application(self, name, repo_url, branch, org_id):
        app_data = {
            "publicId": re.sub(r"[^a-zA-Z0-9-]", "-", name.lower()),
            "name": name,
            "organizationId": org_id,
        }
        r = self._request("POST", "/api/v2/applications", json=app_data)
        if not r:
            return None
        app_id = r.json()["id"]
        source_control_data = {
            "repositoryUrl": repo_url,
            "baseBranch": branch,
            "remediationPullRequestsEnabled": True,
            "pullRequestCommentingEnabled": True,
            "sourceControlEvaluationsEnabled": True,
        }
        sc_r = self._request(
            "POST",
            f"/api/v2/sourceControl/application/{app_id}",
            json=source_control_data,
        )
        return app_id if sc_r else None

    def scan_application(self, app_id, branch, stage_id):
        scan_data = {"stageId": stage_id, "branchName": branch}
        r = self._request(
            "POST",
            f"/api/v2/evaluation/applications/{app_id}/sourceControlEvaluation",
            json=scan_data,
        )
        return r and r.status_code == 200


class AzureDevOps(APIClient):
    def __init__(self, organization, token):
        auth_string = base64.b64encode(f":{token}".encode()).decode()
        super().__init__(
            f"https://dev.azure.com/{organization}",
            headers={
                "Authorization": f"Basic {auth_string}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            verify=False,
        )

    def get_projects(self):
        r = self._request("GET", "/_apis/projects?api-version=7.1")
        return [
            {"id": p["id"], "name": p["name"], "description": p.get("description", "")}
            for p in (r.json().get("value", []) if r else [])
        ]

    def get_repo_url(self, project_id):
        r = self._request(
            "GET", f"/{project_id}/_apis/git/repositories?api-version=7.1"
        )
        repos = r.json().get("value", []) if r else []
        return repos[0].get("remoteUrl") if repos else None


class Sync:
    def __init__(self, config):
        self.config = config
        self.azure = AzureDevOps(
            config["AZURE_DEVOPS_ORGANIZATION"], config["AZURE_DEVOPS_TOKEN"]
        )
        self.iq = IQ(
            config["IQ_SERVER_URL"], config["IQ_USERNAME"], config["IQ_PASSWORD"]
        )

    def sync(self, org_id, chinese_name):
        logger.info(f"🔍 Syncing organization: {chinese_name} (ID: {org_id})")
        projects = [
            p
            for p in self.azure.get_projects()
            if re.search(
                rf"權責部門：{re.escape(chinese_name)}", p.get("description", "")
            )
        ]
        if not projects:
            logger.warning(
                f"⚠️ No matching projects found for organization: {chinese_name}"
            )
            return {"created": 0, "scanned": 0, "errors": 0}

        logger.info(f"✅ Discovered {len(projects)} applications")
        apps = self.iq.get_applications(org_id)
        created = scanned = errors = 0
        branch = self.config.get("DEFAULT_BRANCH", "main")

        with tqdm(
            total=len(projects), desc="⚡ Processing applications", unit="app"
        ) as pbar:
            for p in projects:
                repo_name = p["name"]
                logger.debug(f"Processing project: {repo_name}")
                clone_url = self.azure.get_repo_url(p["id"])
                if not clone_url:
                    logger.warning(
                        f"⚠️ Repository URL not found for project: {repo_name}"
                    )
                    errors += 1
                    pbar.update(1)
                    continue
                app_id = apps.get(repo_name)
                if not app_id:
                    logger.info(f"✨ Creating IQ application: {repo_name}")
                    app_id = self.iq.create_application(
                        repo_name, clone_url, branch, org_id
                    )
                    if not app_id:
                        errors += 1
                        pbar.update(1)
                        continue
                    created += 1
                logger.info(f"🔬 Initiating scan for application: {repo_name}")
                if self.iq.scan_application(app_id, branch, self.config["STAGE_ID"]):
                    scanned += 1
                else:
                    errors += 1
                pbar.update(1)

        logger.info(
            f"🏁 Summary for {chinese_name}: {created} applications created, {scanned} scanned, {errors} errors."
        )
        return {"created": created, "scanned": scanned, "errors": errors}


@handle_main_execution
def sync_repos_main():
    """Main function to run the synchronization process."""
    logger.info("🚀 Starting Azure DevOps to Sonatype IQ synchronization.")
    try:
        config = load_sync_config()
        orgs = load_organizations()
        sync_tool = Sync(config)
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}", exc_info=True)
        return

    total = {"created": 0, "scanned": 0, "errors": 0}

    with tqdm(total=len(orgs), desc="Syncing organizations", unit="org") as pbar:
        for org in orgs:
            pbar.set_description(f"🏢 Processing organization: {org['chineseName']}")
            try:
                result = sync_tool.sync(org["id"], org["chineseName"])
                for k in total:
                    total[k] += result[k]
            except Exception as e:
                total["errors"] += 1
                logger.exception(
                    f"❌ Error processing organization {org['chineseName']}: {e}"
                )
            pbar.update(1)

    logger.info(
        f"🎉 Synchronization complete. Total created: {total['created']}, "
        f"scanned: {total['scanned']}, errors: {total['errors']}."
    )
    if total["errors"] > 0:
        logger.warning(
            "⚠️ Errors occurred during synchronization. See logs for details."
        )


def main():
    """Script entry point."""
    sync_repos_main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    setup_logging()
    logger = get_logger(__name__)
    main()
