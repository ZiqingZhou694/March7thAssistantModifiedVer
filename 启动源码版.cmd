@echo off
chcp 65001 >nul
cd /d "%~dp0"
"C:\Users\jing7\Documents\Codex\venv3145\Scripts\python.exe" app.py
if errorlevel 1 pause
