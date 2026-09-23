@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe launch.py %*
  exit /b
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3.11 launch.py %*
  exit /b
)
where python >nul 2>&1
if not errorlevel 1 (
  python launch.py %*
  exit /b
)
echo Install CPython 3.11 or use docker compose up --build.
exit /b 1
