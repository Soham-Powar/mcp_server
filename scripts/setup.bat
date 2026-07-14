@echo off
REM One-time setup: create venv, install backend deps, seed the database.
setlocal
cd /d "%~dp0.."

echo === Creating virtual environment (.venv) ===
python -m venv .venv
if errorlevel 1 (
  echo Failed to create venv. Is Python 3.10+ installed and on PATH?
  exit /b 1
)

echo === Installing Python dependencies ===
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo === Seeding sample databases (UPI + IMPS) ===
python database\seed.py
python database\imps_seed.py

echo.
echo === Done. To run the backend: ===
echo   .venv\Scripts\activate
echo   uvicorn backend.main:app --reload
echo.
echo === In a second terminal, run the frontend: ===
echo   cd frontend ^&^& npm install ^&^& npm run dev
endlocal
