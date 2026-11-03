#!/bin/bash
cd "$(dirname "$0")"
echo "[1/2] 安装 Python 依赖..."
python3 -m pip install -r requirements.txt || { echo "安装失败：请先安装 Python 3.10+（https://www.python.org/downloads/）"; exit 1; }
echo "[2/2] 下载 Chromium 浏览器（约 150MB，只需一次）..."
python3 -m playwright install chromium || { echo "浏览器下载失败，请检查网络后重试"; exit 1; }
echo
echo "安装完成！双击 run.command 即可启动。"
