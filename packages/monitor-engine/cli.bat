@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0"
set PYTHONPATH=%~dp0..\monitor-cli;%~dp0..\monitor-db;%PYTHONPATH%
"C:\Users\Alex\AppData\Local\Microsoft\WindowsApps\python3.13.exe" "%~dp0..\monitor-cli\cli.py" %*
