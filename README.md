# Repository Recommender

A repositories recommender just like video streamers.
Record users' behaviour and suggest repositories to users.

阶段路线见 ROADMAP.md,背景与共识见 PROJECT_NOTES.md。

## 进度(P0-P9,每阶段 3 行:学会了什么 / 卡在哪 / 下一步)

### P0 环境 + Git —— 完成
- 学会:venv(python3 -m venv .venv && source .venv/bin/activate)、git init/add/commit/remote/push、.gitignore 挡住 token 和数据。
- 卡点:无。
- 下一步:P1 调 GitHub API 拉候选池。

### P1 数据采集(GitHub API)—— 完成
- 学会:HTTP GET + 请求头(Accept / Authorization)、200/403 的含义、search API 分页(per_page=100 + page)、限流与退避(Retry-After / X-RateLimit-Reset)、断点续跑(文件已存在就跳过)。
- 卡点:无 GITHUB_TOKEN 时是未认证额度,搜索接口 10 次/分钟。实测拉到第 5 次就被 403 secondary rate limit 挡住,靠退避等待(41s / 60s)继续跑完,全程 12 次请求 / 4 分 34 秒。
- 结果:6 种语言 × 2 页 = 1200 条记录 → data/raw/*.json(12 个文件)。
- 下一步:P2 入库。

### P2 存储层(SQLite)—— 完成
- 学会:CREATE TABLE / UNIQUE / 索引、ON CONFLICT DO UPDATE(upsert)、参数化查询(? 占位)、SQLite 的 JSON 函数拆 topics、时间统一成 UTC。
- 卡点:typescript 第 1、2 页重复了 2 个 repo(拉页之间等了 2 分钟,星标排序的榜单在动,分页本身不稳定)。被 UNIQUE(full_name) 挡住,1200 条原始记录 → 1198 行。
- 结果:schema.sql + db.py + load_raw.py;repos 表 1198 行,重复跑行数不变(幂等)。
- 下一步:P3 增量快照 + trending 榜。

### P3 增量快照 + trending 榜 —— 代码完成,等第二份快照(验收要连续两天)
- 学会:快照表为什么单独建(repos 的 star 数每天被覆盖,不留历史就算不出增量)、主键 (repo_id, snapshot_date) 怎么天然防重复、SQL 自连接(同一张表当 cur/prev 用,相减得 delta)、heapq.nlargest 取 Top-K、cron 定时任务、一级限流(额度用完)和二级限流(scraping/abuse)的区别与各自退避策略。
- 学会(接口取舍):刷新元数据用 search 重拉(12 次请求),不是逐个 repo 查详情(1193 次)——用量差 100 倍,代价是掉出榜单的 repo 不再被刷新。
- 卡点:未认证限流比 P1 那次更凶,12 次请求被 403 secondary rate limit 反复拦,靠退避(22s/31s/41s/59s)才全部拉回,单轮耗时明显变长。教训:REQUEST_GAP 是被限流额度直接决定的(未认证 10 次/分 → 必须睡 ≥7 秒),已改成按有无 token 自适应;并补了"单个语言失败不拖垮整轮"的容错——定时任务不能因为一个环节崩掉,整天没快照。
- 结果:schema.sql 加 repo_snapshots 表;daily_update.py(拉数据 → upsert repos → 写当天快照);trending.py(自连接算 delta + heapq 取 Top-N)。2026-09-22 第一份快照 1193 行已入库;cron 已配(每天 10:17 本地时间)。
- 待办:P4 同步自己的 star 历史。等 2026-09-23 cron 跑出第二份快照,trending.py 才有真榜可比。
- 注意:WSL 不启动时 cron 不会跑;哪天没跑,trending 会自动拿"最近两个有数据的日期"比,跨度可能变成 2 天。
