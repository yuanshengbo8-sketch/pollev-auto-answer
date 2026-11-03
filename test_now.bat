@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 立刻开始监测 10 分钟（测试用，Ctrl+C 可停止）
python pollev_bot.py --now --minutes 10
pause
