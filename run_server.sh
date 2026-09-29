#!/bin/bash
# 启动服务。端口只在这里写一次 —— 改端口就改这一行,
# 别让它散落在 README、crontab、各种笔记里(那种迟早对不上)。
#
# ⚠️ 改端口的话记得同步改 GitHub OAuth App 里的回调地址,
#    两个必须一致,否则登录会报 redirect_uri mismatch。
PORT=18080

# 绑 0.0.0.0 而不是 127.0.0.1 —— 前者局域网上的其他设备才访问得到
cd /home/diagonalc/repo-recommender || exit 1
mkdir -p logs
echo "服务地址: http://$(hostname -I | awk '{print $1}'):$PORT/"
echo "本机访问: http://127.0.0.1:$PORT/"
exec .venv/bin/uvicorn api:app --host 0.0.0.0 --port "$PORT"
