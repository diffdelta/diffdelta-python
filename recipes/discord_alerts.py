#!/usr/bin/env python3
"""DiffDelta → Discord: Post intelligence alerts to a Discord channel.

Setup (2 minutes):
    1. In Discord: Server Settings → Integrations → Webhooks → New Webhook
       Copy the Webhook URL.
    2. Set the environment variable:
       export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
    3. Run:
       python discord_alerts.py

Polls DiffDelta every 15 minutes and posts new items as rich embeds.
Cursor is saved automatically — you never see the same alert twice.
"""

import os
import sys

import requests
from diffdelta import DiffDelta

# ── Configuration ──────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
TAGS = ["security"]                  # Change to [] for all sources
MIN_RISK_SCORE = 0                   # Set to 7+ to only see critical items
# ───────────────────────────────────────────────────────────────

if not DISCORD_WEBHOOK_URL:
    print("ERROR: Set DISCORD_WEBHOOK_URL environment variable.")
    print("  export DISCORD_WEBHOOK_URL='https://discord.com/api/webhooks/...'")
    sys.exit(1)


def risk_color(score):
    """Map risk score to Discord embed color (decimal)."""
    if score is None:
        return 0x5865F2   # Blurple
    if score >= 9:
        return 0xED4245   # Red
    if score >= 7:
        return 0xFFA500   # Orange
    if score >= 4:
        return 0xFEE75C   # Yellow
    return 0x57F287       # Green


def post_to_discord(item):
    """Format a FeedItem as a Discord embed and post it."""
    risk = item.raw.get("risk_score")

    if risk is not None and risk < MIN_RISK_SCORE:
        return

    embed = {
        "title": item.headline[:256],
        "url": item.url,
        "description": item.excerpt[:400] if item.excerpt else "",
        "color": risk_color(risk),
        "fields": [
            {"name": "Source", "value": f"`{item.source}`", "inline": True},
            {"name": "Bucket", "value": item.bucket, "inline": True},
        ],
        "footer": {"text": "DiffDelta Intelligence Feed"},
    }

    if risk is not None:
        embed["fields"].insert(1, {
            "name": "Risk Score",
            "value": f"{risk}/10",
            "inline": True,
        })

    payload = {
        "embeds": [embed],
        "username": "DiffDelta",
    }

    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    if resp.status_code not in (200, 204):
        print(f"  Discord error ({resp.status_code}): {resp.text}")
    else:
        print(f"  ✅ Posted to Discord: {item.headline[:60]}")


if __name__ == "__main__":
    dd = DiffDelta()
    print(f"🔒 DiffDelta → Discord | Watching {TAGS or 'all'} sources")
    dd.watch(post_to_discord, tags=TAGS if TAGS else None)
