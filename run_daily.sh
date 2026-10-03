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

# ---- 第〇步:先备份 ----
#
# 放在**采集之前**:这样它记下的是"今天动手之前"的状态 ——
# 万一这次采集本身把库写坏了,你有一份干净的可以回退。
# 放后面就晚了,坏数据已经进去了。
#
# 备份失败**不中断整轮** —— 采集数据比留备份更要紧,没道理因为备份不成就放弃采集。
# 但会写一行很显眼的日志:它意味着你现在处于"没有任何备份"的状态。
.venv/bin/python -u backup_db.py >> logs/daily.log 2>&1 \
  || echo "[!] 备份失败 —— 数据库目前没有任何备份,去 logs 里看原因" >> logs/daily.log

# ---- 第一步:采集 + 记快照 ----
.venv/bin/python -u daily_update.py >> logs/daily.log 2>&1
code=$?

# ---- 第二步:给所有登录用户同步 star / 关注 ----
#
# ⚠️ **必须放在采集之后。** 采集(写 repos + 今天的快照)是这条链路上最要紧的一步,
# 而同步是"可能要跑很久"的一步(每个人要翻好几页、每页之间还要 sleep)。
# 顺序反过来,一次同步卡住就会让这天**一份快照都没有** —— 而快照缺一天,
# trending 的增速就永远缺那一天的对比,事后补不回来。
#
# 这一步为什么必须存在:推荐的口味信号来自 star。不同步的话,
# 新登录的人推荐页永远是空的,看起来就像"这站坏了"。
#
# 退出码:sync_all 会**区分两种失败** ——
#   网络类失败(重试有意义)→ 非零,让任务重试
#   token 失效(重试没用)  → 0,不然一个过期 token 会让任务每天白重试三轮
# 详见 sync_all.py 末尾的说明;回归测试在 tests/test_sync_all.py。
#
# 采集本身失败时就不跑同步了 —— 网络都不通,同步也白跑。
sync_code=0
if [ "$code" -eq 0 ]; then
  .venv/bin/python -u sync_all.py >> logs/daily.log 2>&1
  sync_code=$?
else
  echo "--- 采集失败,跳过用户同步 ---" >> logs/daily.log
fi

# 决定这一轮的最终退出码:
#   采集失败       → 用采集的码(让任务重试)
#   采集成功、同步全挂 → 用同步的码(让任务重试)
#   其它           → 0
final=$code
if [ "$code" -eq 0 ] && [ "$sync_code" -ne 0 ]; then
  final=$sync_code
fi

# 把退出码也写进日志:Windows 任务计划程序那边只看得到状态码,
# 看不到输出;留一行在日志里,以后对时间线方便。
echo "--- daily_update=$code sync_all=$sync_code exit=$final $(date -u +%FT%TZ) ---" >> logs/daily.log
exit $final
