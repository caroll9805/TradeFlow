@echo off
REM Runs only the backend pytest suite inside the backend image (no network needed). Output: logs\pytest.log
cd /d "%~dp0"
echo Running backend tests (pytest)...
docker compose run --rm --no-deps backend pytest -v -ra > logs\pytest.log 2>&1
echo exit=%ERRORLEVEL% > logs\pytest.done
type logs\pytest.log
