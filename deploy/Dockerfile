# DiffDelta Agent — runs any recipe as a long-lived container.
#
# Build (from the diffdelta-python root):
#   docker build -f deploy/Dockerfile -t diffdelta-agent .
#
# Run (Slack example):
#   docker run -d --restart=always \
#     -e RECIPE=slack_alerts \
#     -e SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../xxx" \
#     -v diffdelta-cursors:/data \
#     diffdelta-agent
#
# Available recipes: slack_alerts, discord_alerts, github_issues, pagerduty_trigger
#
# The cursor volume (-v diffdelta-cursors:/data) ensures you never
# see duplicate alerts, even if the container restarts.

FROM python:3.12-slim

WORKDIR /app

# Install diffdelta from PyPI
RUN pip install --no-cache-dir diffdelta

# Copy recipes into the image
COPY recipes/ /app/recipes/

# Cursor persistence: store in /data (mount as volume)
ENV DD_CURSOR_PATH=/data/cursors.json

# Default recipe (override with -e RECIPE=...)
ENV RECIPE=slack_alerts

# Entrypoint: run the chosen recipe
CMD python /app/recipes/${RECIPE}.py
