#!/usr/bin/env python3
"""DiffDelta → GitHub Issues: Auto-create issues for high-risk CVEs.

Setup (2 minutes):
    1. Create a GitHub Personal Access Token with 'repo' scope:
       https://github.com/settings/tokens
    2. Set environment variables:
       export GITHUB_TOKEN="ghp_..."
       export GITHUB_REPO="your-org/your-repo"
    3. Run:
       python github_issues.py

Creates a GitHub issue for every new security item with risk score ≥ 7.
Each issue includes the headline, source, risk score, excerpt, and a
link to the original advisory. Labels are auto-created on first run.
"""

import os
import sys

import requests
from diffdelta import DiffDelta

# ── Configuration ──────────────────────────────────────────────
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")       # e.g. "acme/security-tracker"
MIN_RISK_SCORE = 7                                      # Only create issues for high-risk
TAGS = ["security"]
LABEL = "diffdelta-alert"
# ───────────────────────────────────────────────────────────────

if not GITHUB_TOKEN or not GITHUB_REPO:
    print("ERROR: Set GITHUB_TOKEN and GITHUB_REPO environment variables.")
    print("  export GITHUB_TOKEN='ghp_...'")
    print("  export GITHUB_REPO='your-org/your-repo'")
    sys.exit(1)

API_BASE = f"https://api.github.com/repos/{GITHUB_REPO}"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def ensure_label():
    """Create the diffdelta-alert label if it doesn't exist."""
    resp = requests.get(f"{API_BASE}/labels/{LABEL}", headers=HEADERS, timeout=10)
    if resp.status_code == 404:
        requests.post(
            f"{API_BASE}/labels",
            headers=HEADERS,
            json={
                "name": LABEL,
                "color": "d73a4a",
                "description": "Auto-created by DiffDelta security monitor",
            },
            timeout=10,
        )
        print(f"  Created label: {LABEL}")


def risk_badge(score):
    if score >= 9:
        return "🔴 CRITICAL"
    if score >= 7:
        return "🟠 HIGH"
    if score >= 4:
        return "🟡 MEDIUM"
    return "🟢 LOW"


def create_issue(item):
    """Create a GitHub issue for a high-risk security item."""
    risk = item.raw.get("risk_score")

    if risk is None or risk < MIN_RISK_SCORE:
        return

    badge = risk_badge(risk)

    body = (
        f"## {badge} — Risk Score: {risk}/10\n\n"
        f"**Source:** `{item.source}`\n"
        f"**Advisory:** [{item.headline}]({item.url})\n"
        f"**Detected:** {item.published_at or 'Unknown'}\n\n"
        f"---\n\n"
        f"### Summary\n\n"
        f"{item.excerpt or 'No excerpt available.'}\n\n"
        f"---\n\n"
        f"*Auto-created by [DiffDelta](https://diffdelta.io) security monitor.*\n"
    )

    resp = requests.post(
        f"{API_BASE}/issues",
        headers=HEADERS,
        json={
            "title": f"[{item.source}] {item.headline[:200]}",
            "body": body,
            "labels": [LABEL],
        },
        timeout=10,
    )

    if resp.status_code == 201:
        issue_url = resp.json().get("html_url", "")
        print(f"  ✅ Issue created: {issue_url}")
    else:
        print(f"  GitHub error ({resp.status_code}): {resp.text[:200]}")


if __name__ == "__main__":
    ensure_label()
    dd = DiffDelta()
    print(f"🔒 DiffDelta → GitHub Issues | Risk ≥ {MIN_RISK_SCORE}")
    dd.watch(create_issue, tags=TAGS)
