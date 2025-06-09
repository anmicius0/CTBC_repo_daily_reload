#!/usr/bin/env python3
"""
Debug Tool: Remove All Applications from IQ Server Organization
WARNING: This will permanently delete all applications in the specified organization!
"""

import requests
import logging
from typing import List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IQServerClient:
    """Client for Sonatype IQ Server REST API"""

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({"Accept": "application/json"})

    def get_applications(self, org_id: str) -> List[Dict]:
        """Get applications for an organization"""
        response = self.session.get(
            f"{self.base_url}/api/v2/applications/organization/{org_id}"
        )
        response.raise_for_status()
        data = response.json()

        apps_list: List[Dict] = []
        if isinstance(data, dict) and "applications" in data:
            potential_apps = data["applications"]
            if isinstance(potential_apps, list):
                apps_list = [app for app in potential_apps if isinstance(app, dict)]
            else:
                logger.warning(
                    f"IQ API: Expected 'applications' field to be a list, got {type(potential_apps)}"
                )
        elif isinstance(data, list):
            apps_list = [app for app in data if isinstance(app, dict)]
        else:
            logger.warning(
                f"IQ API: Unexpected applications response format: {type(data)}"
            )
        return apps_list

    def delete_application(self, app_id: str) -> bool:
        """Delete application by ID"""
        try:
            response = self.session.delete(
                f"{self.base_url}/api/v2/applications/{app_id}"
            )
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to delete application {app_id}: {e}")
            return False

    def get_organization_by_id(self, org_id: str) -> Dict:
        """Get organization by ID"""
        response = self.session.get(f"{self.base_url}/api/v2/organizations/{org_id}")
        response.raise_for_status()
        return response.json()


def remove_all_applications(
    org_id: str, iq_url: str, iq_username: str, iq_password: str
):
    """Remove all applications from the specified organization"""

    client = IQServerClient(iq_url, iq_username, iq_password)

    try:
        # Verify organization exists
        org = client.get_organization_by_id(org_id)
        logger.info(f"Organization found: {org['name']} (ID: {org_id})")

        # Get all applications
        applications = client.get_applications(org_id)

        if not applications:
            logger.info("No applications found in the organization")
            return

        logger.info(f"Found {len(applications)} applications to delete:")
        for app in applications:
            logger.info(f"  - {app['name']} (ID: {app['id']})")

        # Proceed to delete all applications without confirmation

        # Delete applications
        deleted_count = 0
        failed_count = 0

        for app in applications:
            app_name = app["name"]
            app_id = app["id"]

            logger.info(f"Deleting application: {app_name}")

            if client.delete_application(app_id):
                logger.info(f"✓ Successfully deleted: {app_name}")
                deleted_count += 1
            else:
                logger.error(f"✗ Failed to delete: {app_name}")
                failed_count += 1

        logger.info(f"\nDeletion completed:")
        logger.info(f"  Successfully deleted: {deleted_count}")
        logger.info(f"  Failed to delete: {failed_count}")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.error(f"Organization with ID '{org_id}' not found")
        else:
            logger.error(f"Error accessing organization: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


def main():
    """Main function"""
    # Configuration
    IQ_SERVER_URL = "http://35.208.159.14:8070/"
    IQ_USERNAME = "AdnkEJc8"
    IQ_PASSWORD = "73BNKBGtgt629tEiYP0HyiXxAiLUmRdsrelw0WfM5rVx"
    ORGANIZATION_ID = "a2290a50f45b46b7b5f6df617d5ecf03"

    print("🔧 IQ Server Application Cleanup Tool")
    print("=" * 50)

    remove_all_applications(
        org_id=ORGANIZATION_ID,
        iq_url=IQ_SERVER_URL,
        iq_username=IQ_USERNAME,
        iq_password=IQ_PASSWORD,
    )


if __name__ == "__main__":
    main()
