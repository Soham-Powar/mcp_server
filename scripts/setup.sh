#!/usr/bin/env bash
# One-time setup: create venv, install backend deps, seed the database.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Creating virtual environment (.venv) ==="
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "=== Installing Python dependencies ==="
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "=== Seeding sample databases (UPI + IMPS) ==="
python database/seed.py
python database/imps_seed.py

cat <<'EOF'

=== Done. To run the backend ===
  source .venv/bin/activate
  uvicorn backend.main:app --reload

=== In a second terminal, run the frontend ===
  cd frontend && npm install && npm run dev
EOF
