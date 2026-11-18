@echo off
REM Double-click to run all automated tests inside Docker. Output is saved in logs\
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\test.ps1"
echo Finished with exit code %ERRORLEVEL%. > "%~dp0logs\test.done"
pause
