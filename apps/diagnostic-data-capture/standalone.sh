#!/usr/bin/env bash
set -euo pipefail

# Install before oakapp-base starts nginx; app-layer build steps do not persist
# changes outside /app on every supported oak-agent version.
cp /app/nginx-site.template /etc/nginx/templates/site.template
exec /entrypoint.sh python3 -u /app/main.py --standalone
