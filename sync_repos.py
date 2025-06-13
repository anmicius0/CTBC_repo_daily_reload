import requests
import base64
import logging
from utils import handle_main_execution, load_sync_config, load_organizations


class IQ:
    def __init__(self, url, username, password):
        self.base_url = url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({"Accept": "application/json"})
        self.session.verify = False

    def _request(self, method, endpoint, **kwargs):
        try:
            r = self.session.request(method, f"{self.base_url}{endpoint}", **kwargs)
            r.raise_for_status()
            return r
        except Exception as e:
            logger.error(f"IQ Server API error: {method} {endpoint}: {e}")
            return None

    def get_applications(self, org_id):
        r = self._request("GET", f"/api/v2/applications/organization/{org_id}")
        if r:
            return {a["name"]: a["id"] for a in r.json().get("applications", [])}
        return {}

    def create_application(self, name, repo_url, branch, org_id):
        app_data = {
            "publicId": name.lower().replace(" ", "-"),
            "name": name,
            "organizationId": org_id,
        }
        r = self._request("POST", "/api/v2/applications", json=app_data)
        if not r:
            logger.error(f"Application creation failed: {name}")
            return None
        app_id = r.json()["id"]
        source_control_data = {
            "repositoryUrl": repo_url,
            "baseBranch": branch,
            "remediationPullRequestsEnabled": True,
            "pullRequestCommentingEnabled": True,
            "sourceControlEvaluationsEnabled": True,
        }
        if not self._request(
            "POST",
            f"/api/v2/sourceControl/application/{app_id}",
            json=source_control_data,
        ):
            logger.error(f"Source control configuration failed: {name}")
            return None
        return app_id

    def scan_application(self, app_id, branch, stage_id):
        scan_data = {"stageId": stage_id, "branchName": branch}
        r = self._request(
            "POST",
            f"/api/v2/evaluation/applications/{app_id}/sourceControlEvaluation",
            json=scan_data,
        )
        return r is not None and r.status_code == 200


class AzureDevOps:
    def __init__(self, organization, token):
        self.base_url = f"https://dev.azure.com/{organization}"
        self.session = requests.Session()
        auth_string = base64.b64encode(f":{token}".encode()).decode()
        self.session.headers.update(
            {
                "Authorization": f"Basic {auth_string}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        self.session.verify = False

    def _request(self, method, endpoint, **kwargs):
        try:
            r = self.session.request(method, f"{self.base_url}{endpoint}", **kwargs)
            r.raise_for_status()
            return r
        except Exception as e:
            logger.error(f"Azure DevOps API error: {method} {endpoint}: {e}")
            return None

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
        logger.info(f"Syncing organization: {chinese_name} (ID: {org_id})")
        projects = [
            p
            for p in self.azure.get_projects()
            if f"權責部門：{chinese_name}" in (p.get("description") or "")
        ]
        if not projects:
            logger.warning(
                f"No matching projects found for organization: {chinese_name}"
            )
            return {"created": 0, "scanned": 0, "errors": 0}
        apps = self.iq.get_applications(org_id)
        created = scanned = errors = 0
        branch = self.config.get("DEFAULT_BRANCH", "main")
        for p in projects:
            repo_name = p["name"]
            logger.info(f"Processing project: {repo_name}")
            clone_url = self.azure.get_repo_url(p["id"])
            if not clone_url:
                logger.warning(f"Repository URL not found for project: {repo_name}")
                errors += 1
                continue
            app_id = apps.get(repo_name)
            if not app_id:
                logger.info(f"Creating IQ application: {repo_name}")
                app_id = self.iq.create_application(
                    repo_name, clone_url, branch, org_id
                )
                if not app_id:
                    errors += 1
                    continue
                created += 1
            logger.info(f"Initiating scan for application: {repo_name}")
            if self.iq.scan_application(app_id, branch, self.config["STAGE_ID"]):
                scanned += 1
            else:
                errors += 1
        logger.info(
            f"Summary for {chinese_name}: {created} applications created, {scanned} scanned, {errors} errors."
        )
        return {"created": created, "scanned": scanned, "errors": errors}


def sync_repos_main():
    logger.info("Starting Azure DevOps to Sonatype IQ synchronization.")
    try:
        config = load_sync_config()
        orgs = load_organizations()
        sync_tool = Sync(config)
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        return
    total = {"created": 0, "scanned": 0, "errors": 0}
    for i, org in enumerate(orgs, 1):
        logger.info(f"Processing organization [{i}/{len(orgs)}]: {org['chineseName']}")
        try:
            result = sync_tool.sync(org["id"], org["chineseName"])
            for k in total:
                total[k] += result[k]
        except Exception as e:
            total["errors"] += 1
            logger.exception(f"Error processing organization {org['chineseName']}: {e}")
    logger.info(
        f"Synchronization complete. Total created: {total['created']}, scanned: {total['scanned']}, errors: {total['errors']}."
    )
    if total["errors"] > 0:
        logger.warning(f"Errors occurred during synchronization. See logs for details.")


@handle_main_execution
def run_sync_tool():
    sync_repos_main()


if __name__ == "__main__":
    from utils import setup_logging

    setup_logging()
    logger = logging.getLogger(__name__)
    run_sync_tool()
