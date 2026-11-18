@echo off
REM Double-click to build, start and verify TradeFlow with Docker Desktop. Output is also saved in logs\
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
echo.
echo Finished with exit code %ERRORLEVEL%. > "%~dp0logs\start.done"
pause
