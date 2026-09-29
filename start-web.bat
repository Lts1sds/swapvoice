@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
start "swapvoice-web" /min python -u "%~dp0web_server.py" %*
timeout /t 2 /nobreak >nul
start http://127.0.0.1:8765
