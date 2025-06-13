import requests
import logging
from utils import load_cleanup_config, load_organizations, setup_logging

setup_logging()
logger = logging.getLogger(__name__)


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
        return [
            {"name": a["name"], "id": a["id"]}
            for a in (r.json().get("applications", []) if r else [])
        ]

    def delete_application(self, app_id):
        r = self._request("DELETE", f"/api/v2/applications/{app_id}")
        return r is not None and r.status_code == 204


class Cleanup:
    def __init__(self, config):
        self.iq = IQ(
            config["IQ_SERVER_URL"], config["IQ_USERNAME"], config["IQ_PASSWORD"]
        )

    def cleanup(self, org_id, chinese_name):
        logger.info(f"Cleaning organization: {chinese_name} (ID: {org_id})")
        apps = self.iq.get_applications(org_id)
        if not apps:
            logger.warning(f"No applications found for organization: {chinese_name}")
            return {"deleted": 0, "errors": 0}

        deleted = errors = 0

        for app in apps:
            try:
                if self.iq.delete_application(app["id"]):
                    deleted += 1
                    logger.info(f"Deleted application: {app['name']}")
                else:
                    errors += 1
                    logger.error(f"Failed to delete application: {app['name']}")
            except Exception as e:
                errors += 1
                logger.exception(f"Error deleting application {app['name']}: {e}")

        logger.info(
            f"Summary for {chinese_name}: {deleted} applications deleted, {errors} errors."
        )
        return {"deleted": deleted, "errors": errors}


def cleanup_main():
    logger.info("Starting IQ Server application cleanup.")
    try:
        config = load_cleanup_config()
        orgs = load_organizations()
        cleanup_tool = Cleanup(config)
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        return

    total = {"deleted": 0, "errors": 0}

    for i, org in enumerate(orgs, 1):
        logger.info(f"Processing organization [{i}/{len(orgs)}]: {org['chineseName']}")
        try:
            result = cleanup_tool.cleanup(org["id"], org["chineseName"])
            for k in total:
                total[k] += result[k]
        except Exception as e:
            total["errors"] += 1
            logger.exception(f"Error processing organization {org['chineseName']}: {e}")

    logger.info(
        f"Cleanup complete. Total deleted: {total['deleted']}, errors: {total['errors']}."
    )
    if total["errors"] > 0:
        logger.warning("Errors occurred during cleanup. See logs for details.")


if __name__ == "__main__":
    cleanup_main()
