#!/usr/bin/env python3
"""DiffDelta → Slack: Post security alerts to a Slack channel.

Setup (2 minutes):
    1. Create a Slack Incoming Webhook:
       https://api.slack.com/messaging/webhooks
    2. Set the environment variable:
       export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../xxx"
    3. Run:
       python slack_alerts.py

That's it. The script polls DiffDelta every 15 minutes and posts
new security items to your Slack channel. Cursor is saved automatically
so you never see the same alert twice.
"""

import json
import os
import sys

import requests
from diffdelta import DiffDelta

# ── Configuration ──────────────────────────────────────────────
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
TAGS = ["security"]                  # Change to [] for all sources
MIN_RISK_SCORE = 0                   # Set to 7+ to only see critical items
# ───────────────────────────────────────────────────────────────

if not SLACK_WEBHOOK_URL:
    print("ERROR: Set SLACK_WEBHOOK_URL environment variable.")
    print("  export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/T.../B.../xxx'")
    sys.exit(1)


def risk_emoji(score):
    """Map risk score to emoji."""
    if score is None:
        return "ℹ️"
    if score >= 9:
        return "🔴"
    if score >= 7:
        return "🟠"
    if score >= 4:
        return "🟡"
    return "🟢"


def post_to_slack(item):
    """Format a FeedItem as a Slack message and post it."""
    risk = item.raw.get("risk_score")

    # Skip items below minimum risk score
    if risk is not None and risk < MIN_RISK_SCORE:
        return

    emoji = risk_emoji(risk)
    risk_text = f"Risk: {risk}/10" if risk is not None else ""

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *<{item.url}|{item.headline}>*\n"
                        f"Source: `{item.source}` | {risk_text}\n"
                        f"{item.excerpt[:300] if item.excerpt else ''}",
            },
        },
    ]

    payload = {
        "text": f"{emoji} {item.headline}",  # Fallback for notifications
        "blocks": blocks,
    }

    resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
    if resp.status_code != 200:
        print(f"  Slack error ({resp.status_code}): {resp.text}")
    else:
        print(f"  ✅ Posted to Slack: {item.headline[:60]}")


if __name__ == "__main__":
    dd = DiffDelta()
    print(f"🔒 DiffDelta → Slack | Watching {TAGS or 'all'} sources")
    dd.watch(post_to_slack, tags=TAGS if TAGS else None)
