#!/usr/bin/env python3
"""Universal DiffDelta recipe runner.

Runs any recipe either continuously (default) or once (for cron/k8s).

Usage:
    # Continuous (default — polls every 15 min forever):
    python run.py slack_alerts

    # One-shot (for cron jobs, k8s CronJobs, CI):
    python run.py slack_alerts --once

    # With environment variables:
    SLACK_WEBHOOK_URL=https://... python run.py slack_alerts
"""

import importlib
import sys

from diffdelta import DiffDelta


def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py <recipe_name> [--once]")
        print("Recipes: slack_alerts, discord_alerts, github_issues, pagerduty_trigger")
        sys.exit(1)

    recipe_name = sys.argv[1]
    once = "--once" in sys.argv

    # Import the recipe module
    try:
        recipe = importlib.import_module(f"recipes.{recipe_name}")
    except ModuleNotFoundError:
        print(f"ERROR: Recipe '{recipe_name}' not found.")
        print("Available: slack_alerts, discord_alerts, github_issues, pagerduty_trigger")
        sys.exit(1)

    # Find the callback function (first function that takes an item)
    # Convention: the main callback is the function that posts/creates/triggers
    callback_names = [
        "post_to_slack", "post_to_discord", "create_issue", "trigger_pagerduty",
    ]
    callback = None
    for name in callback_names:
        callback = getattr(recipe, name, None)
        if callback:
            break

    if not callback:
        print(f"ERROR: No known callback found in recipe '{recipe_name}'.")
        sys.exit(1)

    tags = getattr(recipe, "TAGS", None)

    dd = DiffDelta()

    if once:
        # One-shot mode: poll once, process items, exit
        items = dd.poll(tags=tags if tags else None)
        print(f"[diffdelta] One-shot: {len(items)} new item(s)")
        for item in items:
            callback(item)
    else:
        # Continuous mode: watch forever
        dd.watch(callback, tags=tags if tags else None)


if __name__ == "__main__":
    main()
