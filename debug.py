#!/usr/bin/env python3

import os
import sys
import json
import requests
from dotenv import load_dotenv

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
            "IQ_SERVER_URL",
            "IQ_USERNAME",
            "IQ_PASSWORD",
        ]
    }


def ORG():
    return json.load(open(resolve_path("config/org-github.json")))


class IQ:
    def __init__(self, url, u, p):
        self.b = url.rstrip("/")
        self.s = requests.Session()
        self.s.auth = (u, p)
        self.s.headers.update({"Accept": "application/json"})

    def req(self, m, e, **k):
        return self.s.request(m, f"{self.b}{e}", **k)

    def apps(self, oid):
        return [
            {"name": a["name"], "id": a["id"]}
            for a in self.req("GET", f"/api/v2/applications/organization/{oid}").json()[
                "applications"
            ]
        ]

    def delete(self, aid):
        self.req("DELETE", f"/api/v2/applications/{aid}")


class Cleanup:
    def __init__(self, c):
        self.c = c
        self.iq = IQ(c["IQ_SERVER_URL"], c["IQ_USERNAME"], c["IQ_PASSWORD"])

    def cleanup(self, oid, kw):
        print(f"\n=== 🧹 Cleaning organization: {kw} (ID: {oid}) ===")
        apps = self.iq.apps(oid)
        dl = er = 0
        total = len(apps)
        if not apps:
            print(f"⚠️  No applications found for '{kw}'")
            return {"deleted": 0, "errors": 0}
        for i, a in enumerate(apps, 1):
            try:
                self.iq.delete(a["id"])
                dl += 1
                print(f"  🗑️ [{i}/{total}] Deleted: {a['name']}")
            except Exception as e:
                er += 1
                print(f"  ❌ [{i}/{total}] {a['name']} - {e}")
        print(f"--- {kw} summary: 🗑️ {dl} deleted, ❌ {er} errors ---")
        return {"deleted": dl, "errors": er}


def main():
    print("\n==============================")
    print("🧹 IQ Server Application Cleanup Tool")
    print("==============================\n")
    c = CFG()
    orgs = [o for o in ORG() if o.get("chineseName")]  # Only orgs with chineseName
    cl = Cleanup(c)
    total = {k: 0 for k in ["deleted", "errors"]}
    print(f"Processing {len(orgs)} organizations...\n")
    for o in orgs:
        r = cl.cleanup(o["id"], o["chineseName"])
        for k in total:
            total[k] += r[k]
    print("\n==============================")
    print(
        f"🏁 OVERALL SUMMARY: 🗑️ Deleted {total['deleted']} | ❌ Errors {total['errors']}"
    )
    print("==============================\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(0)
    except Exception as e:
        print(f"\nCleanup failed: {e}")
        sys.exit(1)
