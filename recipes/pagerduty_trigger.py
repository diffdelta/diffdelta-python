#!/usr/bin/env python3
"""DiffDelta → PagerDuty: Trigger incidents for critical security events.

Setup (2 minutes):
    1. In PagerDuty: Services → your service → Integrations → Add →
       Events API v2 → copy the Integration Key (Routing Key).
    2. Set the environment variable:
       export PAGERDUTY_ROUTING_KEY="R..."
    3. Run:
       python pagerduty_trigger.py

Triggers a PagerDuty incident for every new item with risk score ≥ 8.
Severity maps to risk score: ≥9 = critical, ≥7 = error, ≥4 = warning.
"""

import os
import sys

import requests
from diffdelta import DiffDelta

# ── Configuration ──────────────────────────────────────────────
PAGERDUTY_ROUTING_KEY = os.environ.get("PAGERDUTY_ROUTING_KEY", "")
MIN_RISK_SCORE = 8                   # Only trigger for critical items
TAGS = ["security"]
# ───────────────────────────────────────────────────────────────

PD_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"

if not PAGERDUTY_ROUTING_KEY:
    print("ERROR: Set PAGERDUTY_ROUTING_KEY environment variable.")
    print("  export PAGERDUTY_ROUTING_KEY='R...'")
    sys.exit(1)


def risk_to_severity(score):
    """Map risk score to PagerDuty severity."""
    if score >= 9:
        return "critical"
    if score >= 7:
        return "error"
    if score >= 4:
        return "warning"
    return "info"


def trigger_pagerduty(item):
    """Send a PagerDuty Events API v2 trigger for a critical item."""
    risk = item.raw.get("risk_score")

    if risk is None or risk < MIN_RISK_SCORE:
        return

    severity = risk_to_severity(risk)

    payload = {
        "routing_key": PAGERDUTY_ROUTING_KEY,
        "event_action": "trigger",
        "dedup_key": f"diffdelta-{item.source}-{item.id}",
        "payload": {
            "summary": f"[DiffDelta] [{item.source}] {item.headline[:200]}",
            "source": f"diffdelta:{item.source}",
            "severity": severity,
            "custom_details": {
                "risk_score": risk,
                "source": item.source,
                "url": item.url,
                "excerpt": item.excerpt[:500] if item.excerpt else "",
                "published_at": item.published_at,
            },
        },
        "links": [
            {"href": item.url, "text": "View Advisory"},
            {"href": "https://diffdelta.io", "text": "DiffDelta Dashboard"},
        ],
    }

    resp = requests.post(PD_EVENTS_URL, json=payload, timeout=10)
    if resp.status_code == 202:
        print(f"  ✅ PagerDuty triggered ({severity}): {item.headline[:60]}")
    else:
        print(f"  PagerDuty error ({resp.status_code}): {resp.text[:200]}")


if __name__ == "__main__":
    dd = DiffDelta()
    print(f"🔒 DiffDelta → PagerDuty | Risk ≥ {MIN_RISK_SCORE}")
    dd.watch(trigger_pagerduty, tags=TAGS)
