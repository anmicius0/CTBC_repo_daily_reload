import os
import sys
import json
import requests
import ssl
import urllib3
from dotenv import load_dotenv
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
    required_keys = ["IQ_SERVER_URL", "IQ_USERNAME", "IQ_PASSWORD"]

    config = {k: os.getenv(k) for k in required_keys}

    # Validate required config
    missing = [k for k, v in config.items() if not v]
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
            return [
                {"name": app["name"], "id": app["id"]}
                for app in response.json()["applications"]
            ]
        except Exception as e:
            logger.error(f"Failed to get applications: {e}")
            return []

    def delete_application(self, app_id):
        """Delete an application."""
        try:
            response = self._request("DELETE", f"/api/v2/applications/{app_id}")
            return response.status_code == 204
        except Exception as e:
            logger.error(f"Failed to delete application {app_id}: {e}")
            return False


logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class Cleanup:
    def __init__(self, config):
        self.config = config
        self.iq = IQ(
            config["IQ_SERVER_URL"], config["IQ_USERNAME"], config["IQ_PASSWORD"]
        )

    def cleanup(self, org_id, chinese_name):
        logger.info(f"=== 🧹 Cleaning organization: {chinese_name} (ID: {org_id}) ===")

        apps = self.iq.get_applications(org_id)
        if not apps:
            logger.warning(f"No applications found for '{chinese_name}'")
            return {"deleted": 0, "errors": 0}

        deleted = errors = 0

        for app in apps:
            try:
                if self.iq.delete_application(app["id"]):
                    deleted += 1
                    logger.info(f"    ✅ Deleted: {app['name']}")
                else:
                    errors += 1
                    logger.error(f"    ❌ Failed to delete: {app['name']}")
            except Exception as e:
                errors += 1
                logger.exception(f"    ❌ Error deleting {app['name']}: {e}")

        logger.info(
            f"--- {chinese_name} summary: 🗑️ {deleted} deleted, ❌ {errors} errors ---"
        )
        return {"deleted": deleted, "errors": errors}


def cleanup_main():
    logger.info("==============================")
    logger.info("🧹 IQ Server Application Cleanup Tool")
    logger.info("==============================")

    try:
        logger.info("Loading configuration...")
        config = load_config()
        logger.info("Configuration loaded successfully")

        logger.info("Loading organizations...")
        orgs = load_organizations()
        logger.info(f"Found {len(orgs)} valid organizations")

        logger.info("Initializing cleanup tool...")
        cleanup_tool = Cleanup(config)
        logger.info("Cleanup tool initialized")

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        return

    total = {"deleted": 0, "errors": 0}

    logger.info(f"📊 Processing {len(orgs)} organizations...")
    for i, org in enumerate(orgs, 1):
        logger.info(
            f"[{i}/{len(orgs)}] 🏢 Processing organization: {org['chineseName']}"
        )
        try:
            result = cleanup_tool.cleanup(org["id"], org["chineseName"])
            for key in total:
                total[key] += result[key]
        except Exception as e:
            total["errors"] += 1
            logger.exception(
                f"Failed to process organization {org['chineseName']}: {e}"
            )

    logger.info("==============================")
    logger.info(
        f"🏁 OVERALL SUMMARY: 🗑️ Deleted {total['deleted']} | ❌ Errors {total['errors']}"
    )
    if total["errors"] > 0:
        logger.warning(f"⚠️  {total['errors']} errors occurred. Check logs for details.")
    logger.info("==============================")


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger(__name__)
    cleanup_main()
