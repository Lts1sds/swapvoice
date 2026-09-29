@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python -u "%~dp0change_voice.py" %*
pause
