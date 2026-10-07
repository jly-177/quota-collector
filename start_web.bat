@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM 千帆签到自建服务地址（qf_service.py 默认监听 8786）；留空则跳过千帆平台
if not defined QF_BASE_URL set "QF_BASE_URL=http://127.0.0.1:8786"

REM Pick an available Python interpreter (prefer the bundled TRAE/WorkBuddy python)
set "PYC="
if exist "C:\Users\Administrator\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe" (
    set "PYC=C:\Users\Administrator\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe"
)
if not defined PYC if exist "C:\Users\54004\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
    set "PYC=C:\Users\54004\.workbuddy\binaries\python\versions\3.13.12\python.exe"
)
if not defined PYC if exist "D:\Dev\python.exe" set "PYC=D:\Dev\python.exe"
if not defined PYC set "PYC=python"

title WorkBuddy Checkin Web Server
echo Starting WorkBuddy checkin web server...
echo (Keep this window open. Press Ctrl+C to stop.)
echo.
"%PYC%" "%~dp0web_server.py"
echo.
echo Server stopped.
pause
