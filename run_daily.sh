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

# ---------- 单实例锁 ----------
# 任务一天触发两次(上午一次、傍晚一次,互为备份 —— 笔记本上午可能在休眠)。
# 万一上一次还没跑完(撞限流时脚本会睡很久,一轮可能几十分钟),这次必须**直接退出**:
# 两个进程同时写同一个 SQLite 会撞 "database is locked",两边都受损。
#
# 用 fd 9 持有锁:脚本一退出 fd 就关,锁自动释放 —— 不需要手动清理,
# 也不怕进程被强杀留下一个"过期的锁文件"把后面的运行全挡死。
exec 9>>logs/daily.lock
if ! flock -n 9; then
  echo "--- 上一次还在跑,这次跳过 $(date -u +%FT%TZ) ---" >> logs/daily.log
  exit 0
fi

# ---------- 日志轮转 ----------
# 这个文件是只追加的,不轮转会一直长。超过 2MB 就留一份上一轮的,其余丢掉。
if [ -f logs/daily.log ] && [ "$(stat -c%s logs/daily.log)" -gt 2097152 ]; then
  mv logs/daily.log logs/daily.log.1
  echo "(日志已轮转,旧的见 logs/daily.log.1)" >> logs/daily.log
fi

# -u = 不缓冲输出。定时任务失败时,日志里能看到它跑到哪一步才断 —— 否则一片空白
# 用 venv 里的 python:项目的依赖(fastapi/sklearn/jieba)都装在那儿,
# 系统 python 是没有的。以后定时任务要跑别的脚本,也一律用这个解释器。
.venv/bin/python -u daily_update.py >> logs/daily.log 2>&1
code=$?

# 把退出码也写进日志:Windows 任务计划程序那边只看得到状态码,
# 看不到输出;留一行在日志里,以后对时间线方便。
echo "--- exit=$code $(date -u +%FT%TZ) ---" >> logs/daily.log
exit $code
