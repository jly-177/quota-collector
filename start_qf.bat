@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "PYC="
if exist "C:\Users\Administrator\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe" (
    set "PYC=C:\Users\Administrator\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe"
)
if exist "C:\Users\54004\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
    set "PYC=C:\Users\54004\.workbuddy\binaries\python\versions\3.13.12\python.exe"
)
if not defined PYC if exist "D:\Dev\python.exe" set "PYC=D:\Dev\python.exe"
if not defined PYC set "PYC=python"

title Qianfan (DuMate) Checkin Service
echo Starting Qianfan signin service on port %QF_SERVICE_PORT% (default 8786)...
echo (Keep this window open. Press Ctrl+C to stop.)
echo.
"%PYC%" "%~dp0qf_service.py"
echo.
echo Service stopped.
pause