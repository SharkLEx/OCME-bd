@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0"
"C:\Users\Alex\AppData\Local\Microsoft\WindowsApps\python3.13.exe" -m monitor_cli %*
