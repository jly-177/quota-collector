@echo off
chcp 65001 >nul
title WorkBuddy Token 捕获工具
cd /d "%~dp0"

echo ============================================================
echo   WorkBuddy 明文 Token 捕获工具
echo ============================================================
echo.
echo 请先确认：
echo   1. WorkBuddy 已完全关闭（包括托盘图标）
echo   2. 准备好后按任意键启动 WorkBuddy（带调试端口）
echo.
pause >nul

echo.
echo 正在启动 WorkBuddy（带调试端口 9222）...
start "" "D:\1\ai\workbuddy\WorkBuddy.exe" --remote-debugging-port=9222

echo.
echo WorkBuddy 正在启动...
echo 请等待 WorkBuddy 完全打开并登录后，
echo 按任意键开始捕获 token...
echo.
pause >nul

echo 开始捕获...
echo.
node capture_wb_token.js

echo.
echo 按任意键退出...
pause >nul
