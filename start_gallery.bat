@echo off
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
    python gallery_server.py
    goto end
)

where py >nul 2>nul
if %errorlevel%==0 (
    py gallery_server.py
    goto end
)

echo Python was not found on this PC.
echo Install it from https://www.python.org/downloads/ and make sure to check "Add Python to PATH" during setup.

:end
pause