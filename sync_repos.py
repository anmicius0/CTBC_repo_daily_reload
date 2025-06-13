import os
import sys
import json
import requests
import ssl
import urllib3
from github import Github
from dotenv import load_dotenv
from error_handler import ErrorHandler

# Globally disable SSL certificate verification
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


def CFG():
    return {
        k: os.getenv(k)
        for k in [
            "GITHUB_TOKEN",
            "IQ_SERVER_URL",
            "IQ_USERNAME",
            "IQ_PASSWORD",
            "GITHUB_SEARCH_QUERY",
        ]
    } | {
        "DEFAULT_BRANCH": os.getenv("DEFAULT_BRANCH", "main"),
        "STAGE_ID": os.getenv("STAGE_ID", "source"),
    }


# Set DEBUG mode from environment variable (default: False)
DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes")


def ORG():
    org_file = "config/debug-org.json" if DEBUG else "config/org-github.json"
    return json.load(open(resolve_path(org_file), encoding="utf-8"))


class IQ:
    def __init__(self, url, u, p):
        self.b = url.rstrip("/")
        self.s = requests.Session()
        self.s.auth = (u, p)
        self.s.headers.update({"Accept": "application/json"})
        self.s.verify = False

    def req(self, m, e, **k):
        try:
            response = self.s.request(m, f"{self.b}{e}", **k)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as http_err:
            # Re-raise with additional context for better error categorization
            raise requests.exceptions.HTTPError(
                f"IQ Server API error ({m} {e}): {http_err}", response=http_err.response
            ) from http_err

    @ErrorHandler.handle_operation("get applications", return_none_on_error=True)
    def apps(self, oid):
        response = self.req("GET", f"/api/v2/applications/organization/{oid}")
        return {a["name"]: a["id"] for a in response.json()["applications"]}

    @ErrorHandler.handle_operation("create application", return_none_on_error=True)
    def create(self, n, url, br, oid):
        # Create application
        app_response = self.req(
            "POST",
            "/api/v2/applications",
            json={
                "publicId": n.lower().replace(" ", "-"),
                "name": n,
                "organizationId": oid,
            },
        )
        app_id = app_response.json()["id"]

        # Configure source control
        self.req(
            "POST",
            f"/api/v2/sourceControl/application/{app_id}",
            json={
                "repositoryUrl": url,
                "baseBranch": br,
                "remediationPullRequestsEnabled": True,
                "pullRequestCommentingEnabled": True,
                "sourceControlEvaluationsEnabled": True,
            },
        )
        return app_id

    @ErrorHandler.handle_operation("scan application", return_none_on_error=True)
    def scan(self, aid, br, stg):
        return self.req(
            "POST",
            f"/api/v2/evaluation/applications/{aid}/sourceControlEvaluation",
            json={"stageId": stg, "branchName": br},
        )


class Sync:
    def __init__(self, c):
        self.c = c
        self.gh = Github(c["GITHUB_TOKEN"])
        self.iq = IQ(c["IQ_SERVER_URL"], c["IQ_USERNAME"], c["IQ_PASSWORD"])

    @ErrorHandler.handle_operation("search repositories", return_none_on_error=True)
    def repos(self, kw):
        user = self.gh.get_user()
        query_template = '"權責部門：{kw}" in:description user:{user}'
        q = query_template.format(kw=kw, user=user.login)
        repositories = self.gh.search_repositories(query=q)

        return [
            {
                "name": r.name,
                "clone_url": r.clone_url,
                "default_branch": r.default_branch or self.c["DEFAULT_BRANCH"],
            }
            for r in repositories
        ]

    def sync(self, oid, kw):
        print(f"\n=== 🏢 Syncing organization: {kw} (ID: {oid}) ===")

        # Get repositories with enhanced error handling
        repos = self.repos(kw)
        if repos is None:  # Error occurred in repos method
            print(f"  ❌ Failed to fetch repositories for '{kw}'")
            return {"created": 0, "scanned": 0, "errors": 1}

        # Get existing applications with enhanced error handling
        apps = self.iq.apps(oid)
        if apps is None:  # Error occurred in apps method
            print(f"  ❌ Failed to fetch applications for organization '{kw}'")
            return {"created": 0, "scanned": 0, "errors": 1}

        cr = sc = er = 0
        total = len(repos)

        if not repos:
            print(f"⚠️  No repositories found for '{kw}'")
            return {"created": 0, "scanned": 0, "errors": 0}

        for i, r in enumerate(repos, 1):
            repo_name = r["name"]
            print(f"  📋 [{i}/{total}] Processing: {repo_name}")

            try:
                # Determine if we need to create or use existing application
                if repo_name not in apps:
                    print(f"    🆕 Creating new application for: {repo_name}")
                    aid = self.iq.create(
                        repo_name, r["clone_url"], r["default_branch"], oid
                    )
                    if aid is None:  # Creation failed
                        er += 1
                        print(f"    ❌ Failed to create application: {repo_name}")
                        continue
                    cr += 1
                    print(f"    ✅ Application created: {repo_name}")
                else:
                    aid = apps[repo_name]
                    print(f"    🔄 Using existing application: {repo_name}")

                # Perform scan with enhanced error handling
                print(f"    🔍 Initiating scan for: {repo_name}")
                scan_result = self.iq.scan(aid, r["default_branch"], self.c["STAGE_ID"])
                if scan_result is None:  # Scan failed
                    er += 1
                    print(f"    ❌ Failed to scan: {repo_name}")
                    continue

                sc += 1
                if repo_name not in apps:
                    print(f"  🟢 [{i}/{total}] Created & scanned: {repo_name}")
                else:
                    print(f"  🔄 [{i}/{total}] Scanned existing: {repo_name}")

            except Exception as e:
                er += 1
                print(
                    f"  ❌ [{i}/{total}] Unexpected error processing {repo_name}: {e}"
                )

        print(f"--- {kw} summary: 🟢 {cr} created, 🔄 {sc} scanned, ❌ {er} errors ---")
        return {"created": cr, "scanned": sc, "errors": er}


@ErrorHandler.handle_config_error
def validate_config():
    """Validate required configuration with enhanced error reporting."""
    c = CFG()
    missing_keys = []

    required_keys = ["GITHUB_TOKEN", "IQ_SERVER_URL", "IQ_USERNAME", "IQ_PASSWORD"]
    for key in required_keys:
        if not c.get(key):
            missing_keys.append(key)

    if missing_keys:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_keys)}"
        )

    # Validate GitHub token format (basic check)
    github_token = c["GITHUB_TOKEN"]
    if github_token and not github_token.startswith(
        ("ghp_", "gho_", "ghu_", "ghs_", "ghr_")
    ):
        print("⚠️  Warning: GitHub token format may be invalid", file=sys.stderr)

    # Validate IQ Server URL format
    iq_url = c["IQ_SERVER_URL"]
    if iq_url and not iq_url.startswith(("http://", "https://")):
        raise ValueError(
            f"IQ_SERVER_URL must start with http:// or https://, got: {iq_url}"
        )

    return c


@ErrorHandler.handle_config_error
def validate_organizations():
    """Validate organization configuration with enhanced error reporting."""
    try:
        orgs = ORG()
        if not orgs:
            raise ValueError("No organizations found in configuration file")

        orgs_with_chinese_name = [o for o in orgs if o.get("chineseName")]
        if not orgs_with_chinese_name:
            raise ValueError(
                "No organizations with 'chineseName' found in configuration"
            )

        # Validate organization structure
        for i, org in enumerate(orgs_with_chinese_name):
            if not org.get("id"):
                raise ValueError(
                    f"Organization at index {i} missing required 'id' field"
                )
            if not isinstance(org["id"], str):
                raise ValueError(
                    f"Organization at index {i} 'id' must be a string, got: {type(org['id'])}"
                )

        return orgs_with_chinese_name

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in organization configuration file: {e}")
    except FileNotFoundError:
        org_file = "config/debug-org.json" if DEBUG else "config/org-github.json"
        raise FileNotFoundError(
            f"Organization configuration file not found: {org_file}"
        )


def sync_repos_main():
    print("\n==============================")
    print("🚀 GitHub → Sonatype IQ Sync Tool")
    print("==============================\n")

    # Validate configuration with enhanced error handling
    print("🔧 Validating configuration...")
    c = validate_config()
    print("✅ Configuration validated")

    # Validate organizations with enhanced error handling
    print("🏢 Validating organizations...")
    orgs = validate_organizations()
    print(f"✅ Found {len(orgs)} valid organizations")

    # Initialize sync with enhanced error handling
    print("🔗 Initializing connections...")
    try:
        s = Sync(c)
        print("✅ Connections initialized")
    except Exception as e:
        print(f"❌ Failed to initialize connections: {e}", file=sys.stderr)
        return

    total = {k: 0 for k in ["created", "scanned", "errors"]}
    print(f"\n📊 Processing {len(orgs)} organizations...\n")

    for i, o in enumerate(orgs, 1):
        print(f"🏢 [{i}/{len(orgs)}] Processing organization: {o['chineseName']}")
        try:
            r = s.sync(o["id"], o["chineseName"])
            for k in total:
                total[k] += r[k]
        except Exception as e:
            total["errors"] += 1
            print(f"❌ Failed to process organization {o['chineseName']}: {e}")

    print("\n==============================")
    print(
        f"🏁 OVERALL SUMMARY: 🟢 Created {total['created']} | 🔄 Scanned {total['scanned']} | ❌ Errors {total['errors']}"
    )
    if total["errors"] > 0:
        print(f"⚠️  {total['errors']} errors occurred. Check logs for details.")
    print("==============================\n")


@ErrorHandler.handle_main_execution
def run_sync_tool():
    sync_repos_main()


if __name__ == "__main__":
    run_sync_tool()
