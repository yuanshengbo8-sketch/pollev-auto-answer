@echo off
chcp 65001 >nul
cd /d "%~dp0"
python pollev_bot.py %*
pause
