#!/usr/bin/env python3
"""
Debug Tool: Remove All Applications from IQ Server Organization
WARNING: This will permanently delete all applications in the specified organization!
"""

import requests
import logging
import json
import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_org_configs():
    """Load organization configurations from org-github.json"""
    try:
        with open("org-github.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError("org-github.json file not found")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in org-github.json")


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
    org_id: str, org_name: str, iq_url: str, iq_username: str, iq_password: str
):
    """Remove all applications from the specified organization"""

    client = IQServerClient(iq_url, iq_username, iq_password)

    try:
        logger.info(f"Processing organization: {org_name} (ID: {org_id})")

        # Get all applications
        applications = client.get_applications(org_id)

        if not applications:
            logger.info("No applications found in the organization")
            return {"deleted": 0, "failed": 0}

        logger.info(f"Found {len(applications)} applications to delete:")
        for app in applications:
            logger.info(f"  - {app['name']} (ID: {app['id']})")

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

        logger.info(f"\nDeletion completed for {org_name}:")
        logger.info(f"  Successfully deleted: {deleted_count}")
        logger.info(f"  Failed to delete: {failed_count}\n")

        return {"deleted": deleted_count, "failed": failed_count}

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.error(f"Organization with ID '{org_id}' not found")
        else:
            logger.error(f"Error accessing organization: {e}")
        return {"deleted": 0, "failed": 0}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"deleted": 0, "failed": 0}


def main():
    """Main function"""
    # Configuration from environment variables
    IQ_SERVER_URL = os.getenv("IQ_SERVER_URL")
    IQ_USERNAME = os.getenv("IQ_USERNAME")
    IQ_PASSWORD = os.getenv("IQ_PASSWORD")

    if not all([IQ_SERVER_URL, IQ_USERNAME, IQ_PASSWORD]):
        logger.error(
            "Missing required environment variables: IQ_SERVER_URL, IQ_USERNAME, IQ_PASSWORD"
        )
        return

    # Type check - these should not be None after the check above
    assert IQ_SERVER_URL is not None
    assert IQ_USERNAME is not None
    assert IQ_PASSWORD is not None

    print("🔧 IQ Server Application Cleanup Tool")
    print("=" * 50)

    try:
        # Load organization configurations
        org_configs = load_org_configs()

        overall_stats = {"deleted": 0, "failed": 0}

        print(f"Processing {len(org_configs)} organizations")
        print("=" * 50)

        for org_config in org_configs:
            org_id = org_config["id"]
            # Use chineseName as org_name for display
            org_name = org_config["chineseName"]

            stats = remove_all_applications(
                org_id=org_id,
                org_name=org_name,
                iq_url=IQ_SERVER_URL,
                iq_username=IQ_USERNAME,
                iq_password=IQ_PASSWORD,
            )

            # Accumulate overall statistics
            overall_stats["deleted"] += stats["deleted"]
            overall_stats["failed"] += stats["failed"]

        # Final summary
        print("=" * 50)
        print("OVERALL CLEANUP SUMMARY")
        print("=" * 20)
        print(f"Total applications deleted: {overall_stats['deleted']}")
        print(f"Total deletion failures: {overall_stats['failed']}")
        print("Multi-organization cleanup completed!")

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")


if __name__ == "__main__":
    main()
