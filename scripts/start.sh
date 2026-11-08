#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; source .env; set +a; fi
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check --timeout 15 --retries 1 -r requirements.txt
NODE_USE_SYSTEM_CA=1 npm ci --prefix frontend --fetch-timeout=20000 --fetch-retries=1
npm run build --prefix frontend
.venv/bin/python -m backend.seed
exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "${PORT:-8010}"
