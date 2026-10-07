@echo off
cd /d "%~dp0"
title Qoder Keeper - do not close
"C:\Users\Administrator\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe" -X utf8 qoder_keeper.py --loop >> qoder_keeper.out.log 2>&1
echo [keeper exited] >> qoder_keeper.out.log
