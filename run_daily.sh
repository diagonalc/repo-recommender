#!/bin/bash
# 每日更新的入口脚本 —— 给 Windows 任务计划程序调用。
#
# 为什么不直接让任务去跑 python:
#   任务是从 Windows 侧启动 WSL 的,命令行要穿过 Windows → wsl.exe → bash 好几层,
#   引号和重定向在这种传递里极易出错。把逻辑放进这个脚本,任务那边就只剩一行
#   简单命令,风险全挡在能版本管理的文件里。
set -u

cd /home/diagonalc/repo-recommender || exit 1
mkdir -p logs

# -u = 不缓冲输出。定时任务失败时,日志里能看到它跑到哪一步才断 —— 否则一片空白
/usr/bin/python3 -u daily_update.py >> logs/daily.log 2>&1
code=$?

echo "--- exit=$code $(date -u +%FT%TZ) ---" >> logs/daily.log
exit $code
