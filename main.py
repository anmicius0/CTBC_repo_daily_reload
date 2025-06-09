#!/usr/bin/env python3
"""GitHub to Sonatype IQ Server Repository Sync Tool"""

import requests
import os
import sys
from github import Github
from dotenv import load_dotenv
from typing import Dict, List

load_dotenv()


def get_config():
    """Load configuration from environment variables"""
    config = {
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
        "IQ_SERVER_URL": os.getenv("IQ_SERVER_URL"),
        "IQ_USERNAME": os.getenv("IQ_USERNAME"),
        "IQ_PASSWORD": os.getenv("IQ_PASSWORD"),
        "ORGANIZATION_ID": os.getenv("ORGANIZATION_ID"),
        "SEARCH_TERM": os.getenv("REPOSITORY_SEARCH_TERM", "vintage"),
        "DEFAULT_BRANCH": os.getenv("DEFAULT_BRANCH", "main"),
        "STAGE_ID": os.getenv("STAGE_ID", "source"),
    }

    missing = [
        k
        for k, v in config.items()
        if not v
        and k
        in [
            "GITHUB_TOKEN",
            "IQ_SERVER_URL",
            "IQ_USERNAME",
            "IQ_PASSWORD",
            "ORGANIZATION_ID",
        ]
    ]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return config


class IQServerClient:
    """Simplified IQ Server API client"""

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({"Accept": "application/json"})

    def _request(self, method: str, endpoint: str, **kwargs):
        """Make API request with error handling"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def get_applications(self, org_id: str) -> Dict[str, str]:
        """Get existing applications as name->id mapping"""
        response = self._request("GET", f"/api/v2/applications/organization/{org_id}")
        apps = response.json()["applications"]
        return {app["name"]: app["id"] for app in apps}

    def create_app_with_scm(
        self, repo_name: str, repo_url: str, branch: str, org_id: str
    ) -> str:
        """Create application and add SCM connection in one step"""
        # Create application
        app_data = {
            "publicId": repo_name.lower().replace(" ", "-"),
            "name": repo_name,
            "organizationId": org_id,
        }
        response = self._request("POST", "/api/v2/applications", json=app_data)
        app_id = response.json()["id"]

        # Add SCM connection
        scm_data = {
            "repositoryUrl": repo_url,
            "baseBranch": branch,
            "remediationPullRequestsEnabled": True,
            "pullRequestCommentingEnabled": True,
            "sourceControlEvaluationsEnabled": True,
        }
        self._request(
            "POST", f"/api/v2/sourceControl/application/{app_id}", json=scm_data
        )

        return app_id

    def trigger_scan(self, app_id: str, branch: str, stage_id: str) -> None:
        """Trigger source control evaluation"""
        scan_data = {"stageId": stage_id, "branchName": branch}
        self._request(
            "POST",
            f"/api/v2/evaluation/applications/{app_id}/sourceControlEvaluation",
            json=scan_data,
        )


class GitHubRepoSync:
    """Main synchronization class"""

    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.github = Github(config["GITHUB_TOKEN"])
        self.iq_client = IQServerClient(
            config["IQ_SERVER_URL"], config["IQ_USERNAME"], config["IQ_PASSWORD"]
        )

    def get_repositories(self) -> List[Dict[str, str]]:
        """Get GitHub repositories matching search term"""
        print("Searching GitHub repositories...")
        user = self.github.get_user()
        search_results = self.github.search_repositories(
            query=f"{self.config['SEARCH_TERM']} in:name user:{user.login}"
        )

        repos = []
        for repo in search_results:
            repos.append(
                {
                    "name": repo.name,
                    "clone_url": repo.clone_url,
                    "default_branch": repo.default_branch
                    or self.config["DEFAULT_BRANCH"],
                }
            )

        print(
            f"Found {len(repos)} repositories matching '{self.config['SEARCH_TERM']}'"
        )
        if repos:
            print("Repositories found:")
            for repo in repos:
                print(f"  • {repo['name']} ({repo['default_branch']})")
        return repos

    def sync(self) -> Dict[str, int]:
        """Main sync function"""
        print("GitHub to IQ Server Sync Tool")
        print("=" * 40)
        print("Starting repository synchronization...")

        # Get repositories
        repos = self.get_repositories()
        if not repos:
            print(f"No repositories found matching '{self.config['SEARCH_TERM']}'")
            return {"created": 0, "scanned": 0, "errors": 0}

        # Get existing applications
        print("Checking existing IQ Server applications...")
        existing_apps = self.iq_client.get_applications(self.config["ORGANIZATION_ID"])
        print(f"Found {len(existing_apps)} existing applications in IQ Server")

        # Process repositories
        created = scanned = errors = 0
        total = len(repos)
        print(f"Processing {total} repositories:")

        for i, repo in enumerate(repos, 1):
            repo_name = repo["name"]
            try:
                # Create app if it doesn't exist
                if repo_name not in existing_apps:
                    app_id = self.iq_client.create_app_with_scm(
                        repo_name,
                        repo["clone_url"],
                        repo["default_branch"],
                        self.config["ORGANIZATION_ID"],
                    )
                    print(f"✅ [{i}/{total}] Created & connected: {repo_name}")
                    created += 1
                else:
                    app_id = existing_apps[repo_name]
                    print(f"🔄 [{i}/{total}] Scanning existing: {repo_name}")

                # Trigger scan
                self.iq_client.trigger_scan(
                    app_id, repo["default_branch"], self.config["STAGE_ID"]
                )
                scanned += 1

            except Exception as e:
                print(f"❌ [{i}/{total}] Failed: {repo_name} - {e}")
                errors += 1

        # Summary
        print("\nSync Summary")
        print("=" * 20)
        print(f"Applications created: {created}")
        print(f"Scans triggered: {scanned}")
        print(f"Errors: {errors}")
        print("Synchronization completed!")

        return {"created": created, "scanned": scanned, "errors": errors}


def main():
    """Main function"""
    try:
        config = get_config()
        sync_tool = GitHubRepoSync(config)
        return sync_tool.sync()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nSync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
