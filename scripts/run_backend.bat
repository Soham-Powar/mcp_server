@echo off
REM Start the FastAPI backend (spawns the MCP server over stdio automatically).
cd /d "%~dp0.."

if not exist "database\upi.db" (
  echo No UPI database found - seeding sample data...
  python database\seed.py
)
if not exist "database\imps.db" (
  echo No IMPS database found - seeding sample data...
  python database\imps_seed.py
)

uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
