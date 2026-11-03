#!/bin/bash
cd "$(dirname "$0")"
echo "立刻开始监测 10 分钟（测试用，Ctrl+C 可停止）"
python3 pollev_bot.py --now --minutes 10
