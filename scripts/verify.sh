#!/usr/bin/env bash
# Start a separate server first; see README. Never points the suite at the quick-start database.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; source .env; set +a; fi
export MYSQL_DATABASE=certificate_admin_test
export BASE_URL="${BASE_URL:-http://127.0.0.1:8011}"
.venv/bin/python scripts/acceptance.py
