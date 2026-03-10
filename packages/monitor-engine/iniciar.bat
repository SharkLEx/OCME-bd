@echo off
chcp 65001 > nul
title OCME bd Monitor Engine
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo.
echo  =====================================
echo   OCME bd Monitor Engine
echo  =====================================
echo.
echo  Iniciando bot Telegram...
echo  Para parar: Ctrl+C
echo.

cd /d "%~dp0"
"C:\Users\Alex\AppData\Local\Microsoft\WindowsApps\python3.13.exe" -m monitor_bot.bot

pause
