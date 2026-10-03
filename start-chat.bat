@echo off
rem Opens the chat page through a local proxy (needs Python: https://www.python.org/ or "winget install Python.Python.3.12").
cd /d "%~dp0"
python serve.py --proxy %*
if errorlevel 1 pause
