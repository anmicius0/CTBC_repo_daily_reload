import multiprocessing
import requests
from tqdm import tqdm
from utils import load_cleanup_config, load_organizations, handle_main_execution
from log import get_logger, setup_logging
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings

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
        logger.info(f"🧹 Cleaning organization: {chinese_name} (ID: {org_id})")
        apps = self.iq.get_applications(org_id)
        if not apps:
            logger.warning(f"⚠️ No applications found for organization: {chinese_name}")
            return {"deleted": 0, "errors": 0}

        deleted = errors = 0

        with tqdm(total=len(apps), desc="🗑️ Deleting applications", unit="app") as pbar:
            for app in apps:
                app_name = app["name"]
                try:
                    if self.iq.delete_application(app["id"]):
                        deleted += 1
                        logger.debug(f"Deleted application: {app_name}")
                    else:
                        errors += 1
                        logger.error(f"❌ Failed to delete application: {app_name}")
                except Exception as e:
                    errors += 1
                    logger.exception(f"❌ Error deleting application {app_name}: {e}")
                pbar.update(1)

        logger.info(
            f"🏁 Summary for {chinese_name}: {deleted} applications deleted, {errors} errors."
        )
        return {"deleted": deleted, "errors": errors}


@handle_main_execution
def cleanup_main():
    """Main function to run the cleanup process."""
    logger.info("🚀 Starting IQ Server application cleanup.")
    try:
        config = load_cleanup_config()
        orgs = load_organizations()
        cleanup_tool = Cleanup(config)
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}", exc_info=True)
        return

    total = {"deleted": 0, "errors": 0}

    with tqdm(total=len(orgs), desc="Cleaning organizations", unit="org") as pbar:
        for org in orgs:
            pbar.set_description(f"🏢 Processing organization: {org['chineseName']}")
            try:
                result = cleanup_tool.cleanup(org["id"], org["chineseName"])
                for k in total:
                    total[k] += result[k]
            except Exception as e:
                total["errors"] += 1
                logger.exception(
                    f"❌ Error processing organization {org['chineseName']}: {e}"
                )
            pbar.update(1)

    logger.info(
        f"🎉 Cleanup complete. Total deleted: {total['deleted']}, errors: {total['errors']}."
    )
    if total["errors"] > 0:
        logger.warning("⚠️ Errors occurred during cleanup. See logs for details.")


def main():
    """Script entry point."""
    cleanup_main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    setup_logging()
    logger = get_logger(__name__)
    main()
