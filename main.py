#!/usr/bin/env python3

import os, sys, json, requests
from github import Github
from dotenv import load_dotenv

base_dir = (
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)
resolve_path = lambda p: p if os.path.isabs(p) else os.path.join(base_dir, p)
load_dotenv(resolve_path(".env"))

CFG = lambda: {
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
ORG = lambda: json.load(open(resolve_path("org-github.json")))


class IQ:
    def __init__(self, url, u, p):
        self.b = url.rstrip("/")
        self.s = requests.Session()
        self.s.auth = (u, p)
        self.s.headers.update({"Accept": "application/json"})

    def req(self, m, e, **k):
        return self.s.request(m, f"{self.b}{e}", **k)

    def apps(self, oid):
        return {
            a["name"]: a["id"]
            for a in self.req("GET", f"/api/v2/applications/organization/{oid}").json()[
                "applications"
            ]
        }

    def create(self, n, url, br, oid):
        a = self.req(
            "POST",
            "/api/v2/applications",
            json={
                "publicId": n.lower().replace(" ", "-"),
                "name": n,
                "organizationId": oid,
            },
        ).json()["id"]
        self.req(
            "POST",
            f"/api/v2/sourceControl/application/{a}",
            json={
                "repositoryUrl": url,
                "baseBranch": br,
                "remediationPullRequestsEnabled": True,
                "pullRequestCommentingEnabled": True,
                "sourceControlEvaluationsEnabled": True,
            },
        )
        return a

    def scan(self, aid, br, stg):
        self.req(
            "POST",
            f"/api/v2/evaluation/applications/{aid}/sourceControlEvaluation",
            json={"stageId": stg, "branchName": br},
        )


class Sync:
    def __init__(self, c):
        self.c = c
        self.gh = Github(c["GITHUB_TOKEN"])
        self.iq = IQ(c["IQ_SERVER_URL"], c["IQ_USERNAME"], c["IQ_PASSWORD"])

    def repos(self, kw):
        user = self.gh.get_user()
        query_template = (
            self.c.get("GITHUB_SEARCH_QUERY")
            or '"權責部門：{kw}" in:description user:{user}'
        )
        q = query_template.format(kw=kw, user=user.login)
        return [
            {
                "name": r.name,
                "clone_url": r.clone_url,
                "default_branch": r.default_branch or self.c["DEFAULT_BRANCH"],
            }
            for r in self.gh.search_repositories(query=q)
        ]

    def sync(self, oid, kw):
        print(f"\n=== 🏢 Syncing organization: {kw} (ID: {oid}) ===")
        repos = self.repos(kw)
        apps = self.iq.apps(oid)
        cr = sc = er = 0
        total = len(repos)
        if not repos:
            print(f"⚠️  No repositories found for '{kw}'")
            return {"created": 0, "scanned": 0, "errors": 0}
        for i, r in enumerate(repos, 1):
            try:
                aid = (
                    self.iq.create(r["name"], r["clone_url"], r["default_branch"], oid)
                    if r["name"] not in apps
                    else apps[r["name"]]
                )
                self.iq.scan(aid, r["default_branch"], self.c["STAGE_ID"])
                if r["name"] not in apps:
                    cr += 1
                    print(f"  🟢 [{i}/{total}] Created & scanned: {r['name']}")
                else:
                    print(f"  🔄 [{i}/{total}] Scanned existing: {r['name']}")
                sc += 1
            except Exception as e:
                er += 1
                print(f"  ❌ [{i}/{total}] {r['name']} - {e}")
        print(f"--- {kw} summary: 🟢 {cr} created, 🔄 {sc} scanned, ❌ {er} errors ---")
        return {"created": cr, "scanned": sc, "errors": er}


def main():
    print("\n==============================")
    print("🚀 GitHub → Sonatype IQ Sync Tool")
    print("==============================\n")
    c = CFG()
    orgs = [o for o in ORG() if o.get("chineseName")]  # Only orgs with chineseName
    s = Sync(c)
    total = {k: 0 for k in ["created", "scanned", "errors"]}
    print(f"Processing {len(orgs)} organizations...\n")
    for o in orgs:
        r = s.sync(o["id"], o["chineseName"])
        for k in total:
            total[k] += r[k]
    print("\n==============================")
    print(
        f"🏁 OVERALL SUMMARY: 🟢 Created {total['created']} | 🔄 Scanned {total['scanned']} | ❌ Errors {total['errors']}"
    )
    print("==============================\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(0)
    except Exception as e:
        print(f"\nSync failed: {e}")
        sys.exit(1)
