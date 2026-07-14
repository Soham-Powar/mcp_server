#!/usr/bin/env bash
# Start the FastAPI backend (spawns the MCP server over stdio automatically).
set -euo pipefail
cd "$(dirname "$0")/.."

# Seed the DBs on first run.
if [ ! -f "database/upi.db" ]; then
  echo "No UPI database found — seeding sample data…"
  python database/seed.py
fi
if [ ! -f "database/imps.db" ]; then
  echo "No IMPS database found — seeding sample data…"
  python database/imps_seed.py
fi

exec uvicorn backend.main:app \
  --host "${BACKEND_HOST:-127.0.0.1}" \
  --port "${BACKEND_PORT:-8000}" \
  --reload
