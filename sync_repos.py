import os
import sys
import json
import requests
import ssl
import urllib3
import base64
from dotenv import load_dotenv
from error_handler import ErrorHandler
import logging

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base_dir = (
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)


def resolve_path(p):
    return p if os.path.isabs(p) else os.path.join(base_dir, p)


load_dotenv(resolve_path("config/.env"))


DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes")


def load_config():
    """Load and validate configuration."""
    required_keys = [
        "AZURE_DEVOPS_TOKEN",
        "AZURE_DEVOPS_ORGANIZATION",
        "IQ_SERVER_URL",
        "IQ_USERNAME",
        "IQ_PASSWORD",
    ]

    config = {k: os.getenv(k) for k in required_keys}
    config.update(
        {
            "DEFAULT_BRANCH": os.getenv("DEFAULT_BRANCH", "main"),
            "STAGE_ID": os.getenv("STAGE_ID", "source"),
        }
    )

    # Validate required config
    missing = [k for k, v in config.items() if not v and k in required_keys]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return config


def load_organizations():
    """Load organizations from config file."""
    org_file = "config/debug-org.json" if DEBUG else "config/org-azure.json"
    try:
        with open(resolve_path(org_file), encoding="utf-8") as f:
            orgs = json.load(f)

        valid_orgs = [o for o in orgs if o.get("id") and o.get("chineseName")]
        if not valid_orgs:
            raise ValueError("No valid organizations found in configuration")

        return valid_orgs
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Organization configuration file not found: {org_file}"
        )
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in organization configuration: {e}")


class IQ:
    def __init__(self, url, username, password):
        self.base_url = url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({"Accept": "application/json"})
        self.session.verify = False

    def _request(self, method, endpoint, **kwargs):
        """Make authenticated request to IQ Server."""
        try:
            response = self.session.request(
                method, f"{self.base_url}{endpoint}", **kwargs
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"IQ Server API error ({method} {endpoint}): {e}")
            raise

    def get_applications(self, org_id):
        """Get all applications for an organization."""
        try:
            response = self._request(
                "GET", f"/api/v2/applications/organization/{org_id}"
            )
            return {app["name"]: app["id"] for app in response.json()["applications"]}
        except Exception as e:
            logger.error(f"Failed to get applications: {e}")
            return {}

    def create_application(self, name, repo_url, branch, org_id):
        """Create a new application with source control configuration."""
        try:
            # Create application
            app_data = {
                "publicId": name.lower().replace(" ", "-"),
                "name": name,
                "organizationId": org_id,
            }
            response = self._request("POST", "/api/v2/applications", json=app_data)
            app_id = response.json()["id"]

            # Configure source control
            source_control_data = {
                "repositoryUrl": repo_url,
                "baseBranch": branch,
                "remediationPullRequestsEnabled": True,
                "pullRequestCommentingEnabled": True,
                "sourceControlEvaluationsEnabled": True,
            }
            self._request(
                "POST",
                f"/api/v2/sourceControl/application/{app_id}",
                json=source_control_data,
            )
            return app_id
        except Exception as e:
            logger.error(f"Failed to create application {name}: {e}")
            return None

    def scan_application(self, app_id, branch, stage_id):
        """Initiate a scan for an application."""
        try:
            scan_data = {"stageId": stage_id, "branchName": branch}
            response = self._request(
                "POST",
                f"/api/v2/evaluation/applications/{app_id}/sourceControlEvaluation",
                json=scan_data,
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to scan application {app_id}: {e}")
            return False


class AzureDevOps:
    def __init__(self, organization, token):
        self.organization = organization
        self.base_url = f"https://dev.azure.com/{organization}"
        self.session = requests.Session()

        # Azure DevOps uses basic auth with PAT
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
        """Make a request to Azure DevOps API"""
        try:
            response = self.session.request(
                method, f"{self.base_url}{endpoint}", **kwargs
            )
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            logger.error(f"Azure DevOps API error ({method} {endpoint}): {e}")
            raise

    def get_projects(self):
        """Get projects from Azure DevOps"""
        try:
            endpoint = "/_apis/projects?api-version=7.1"
            response = self._request("GET", endpoint)
            projects = response.json().get("value", [])

            return [
                {
                    "id": project["id"],
                    "name": project["name"],
                    "description": project.get("description", ""),
                }
                for project in projects
            ]
        except Exception as e:
            logger.error(f"Failed to get projects: {e}")
            return []

    def get_repo_url(self, project_id):
        """Get repository URL for a specific project"""
        try:
            endpoint = f"/{project_id}/_apis/git/repositories?api-version=7.1"
            response = self._request("GET", endpoint)
            repos_list = response.json().get("value", [])
            if repos_list:
                logger.debug(f"Repo URL: {repos_list[0].get('remoteUrl')}")
                return repos_list[0].get("remoteUrl")
            return None
        except Exception as e:
            logger.error(f"Failed to get repo URL for project {project_id}: {e}")
            return None


class Sync:
    def __init__(self, config):
        self.config = config
        self.azure_devops = AzureDevOps(
            config["AZURE_DEVOPS_ORGANIZATION"], config["AZURE_DEVOPS_TOKEN"]
        )
        self.iq = IQ(
            config["IQ_SERVER_URL"], config["IQ_USERNAME"], config["IQ_PASSWORD"]
        )

    def sync(self, org_id, chinese_name):
        logger.info(f"=== Syncing organization: {chinese_name} (ID: {org_id}) ===")

        # Get all projects from Azure DevOps
        all_projects = self.azure_devops.get_projects() or []

        # Filter projects that match the organization
        matched_projects = [
            p
            for p in all_projects
            if f"權責部門：{chinese_name}" in (p.get("description") or "")
        ]

        if not matched_projects:
            logger.warning(f"No matching projects found for {chinese_name}")
            return {"created": 0, "scanned": 0, "errors": 0}

        # Get existing applications from IQ Server
        apps = self.iq.get_applications(org_id) or {}

        created = scanned = errors = 0
        default_branch = self.config.get("DEFAULT_BRANCH", "main")

        for project in matched_projects:
            repo_name = project["name"]
            logger.info(f"  Processing: {repo_name}")

            # Get repository URL
            clone_url = self.azure_devops.get_repo_url(project["id"])
            if not clone_url:
                logger.warning(f"    No repository URL found for: {repo_name}")
                errors += 1
                continue

            try:
                app_id = apps.get(repo_name)

                # Create application if it doesn't exist
                if not app_id:
                    logger.info(f"    Creating new application for: {repo_name}")
                    app_id = self.iq.create_application(
                        repo_name, clone_url, default_branch, org_id
                    )
                    if not app_id:
                        errors += 1
                        logger.error(f"    Failed to create application: {repo_name}")
                        continue
                    created += 1

                # Scan the application
                logger.info(f"    Initiating scan for: {repo_name}")
                scan_success = self.iq.scan_application(
                    app_id, default_branch, self.config["STAGE_ID"]
                )
                if not scan_success:
                    errors += 1
                    logger.error(f"    Failed to scan: {repo_name}")
                    continue
                scanned += 1

            except Exception as e:
                errors += 1
                logger.exception(f"  ❌ Unexpected error processing {repo_name}: {e}")

        logger.info(
            f"--- {chinese_name} summary: 🟢 {created} created, 🔄 {scanned} scanned, ❌ {errors} errors ---"
        )
        return {"created": created, "scanned": scanned, "errors": errors}


def sync_repos_main():
    logger.info("==============================")
    logger.info("Azure DevOps → Sonatype IQ Sync Tool")
    logger.info("==============================")

    try:
        logger.info("Loading configuration...")
        config = load_config()
        logger.info("Configuration loaded successfully")

        logger.info("Loading organizations...")
        orgs = load_organizations()
        logger.info(f"Found {len(orgs)} valid organizations")

        logger.info("Initializing connections...")
        sync_tool = Sync(config)
        logger.info("Connections initialized")

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        return

    total = {"created": 0, "scanned": 0, "errors": 0}

    logger.info(f"Processing {len(orgs)} organizations...")
    for i, org in enumerate(orgs, 1):
        logger.info(f"[{i}/{len(orgs)}] Processing organization: {org['chineseName']}")
        try:
            result = sync_tool.sync(org["id"], org["chineseName"])
            for key in total:
                total[key] += result[key]
        except Exception as e:
            total["errors"] += 1
            logger.exception(
                f"Failed to process organization {org['chineseName']}: {e}"
            )

    logger.info("==============================")
    logger.info(
        f"OVERALL SUMMARY: Created {total['created']} | Scanned {total['scanned']} | Errors {total['errors']}"
    )
    if total["errors"] > 0:
        logger.warning(f"{total['errors']} errors occurred. Check logs for details.")
    logger.info("==============================\n")


@ErrorHandler.handle_main_execution
def run_sync_tool():
    sync_repos_main()


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger(__name__)
    run_sync_tool()
