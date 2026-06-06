@echo off
chcp 65001 >nul
cd /d "%~dp0"
"D:\ballbs\.venv\Scripts\python.exe" "%~dp0realm_gui.py"
if errorlevel 1 pause
