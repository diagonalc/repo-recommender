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

### P3 增量快照 + trending 榜 —— 完成(2026-09-28)
- 学会:快照表为什么单独建(repos 的 star 数每天被覆盖,不留历史就算不出增量)、主键 (repo_id, snapshot_date) 怎么天然防重复、SQL 自连接(同一张表当 cur/prev 用,相减得 delta)、heapq.nlargest 取 Top-K、一级限流(额度用完)和二级限流(scraping/abuse)的区别与各自退避策略。
- 学会(接口取舍):刷新元数据用 search 重拉(12 次请求),不是逐个 repo 查详情(1200 次)——用量差 100 倍,代价是掉出榜单的 repo 不再被刷新。
- 学会(定时任务,踩得最狠的一课):**WSL 里的 cron 在 Windows 上根本不可靠** —— WSL 不启动它就不存在,结果 9/22 配的 cron 六天一次都没跑,一天快照都没攒下。改用 **Windows 任务计划程序**(它能主动把 WSL 拉起来)。两个坑:.bat 必须是 **CRLF** 换行,且要用 **wsl.exe 全路径**(任务计划的 PATH 里没有它),否则任务报"成功"但什么都没发生。
- 学会(真 bug):**repo 会改名**。id 不变、full_name 变了,而 upsert 原来只处理 full_name 冲突 → 撞 id 主键,sqlite3.IntegrityError,整批写不进去。db.py 原注释写"id 撞了几乎不可能",六天真实数据就打脸了。已把冲突目标改成 id(它就是身份),full_name 当普通字段更新——改名不断历史。
- 卡点:未认证限流比 P1 那次更凶,12 次请求被 403 secondary rate limit 反复拦,靠退避才全部拉回。教训:REQUEST_GAP 是被限流额度直接决定的(未认证 10 次/分 → 必须睡 ≥7 秒),已改成按有无 token 自适应;并补了"单个语言失败不拖垮整轮"的容错。
- 结果:schema.sql 加 repo_snapshots 表;daily_update.py(拉数据 → upsert repos → 写当天快照,支持 --from-raw 免联网重试);trending.py(自连接算 delta + heapq 取 Top-N);run_daily.sh(定时任务入口)。快照:2026-09-22(1193)+ 2026-09-28(1196),真实榜单已出。
- 定时:Windows 任务计划 `RepoRecommenderDaily`,每天 10:17 → 调 C:\Users\Lenovo\repo-recommender-daily.bat → WSL 里跑 run_daily.sh,日志在 logs/daily.log。
- token:脚本优先读环境变量 GITHUB_TOKEN,没有就读 ~/.config/repo-recommender/token(在仓库外,不可能被提交)。
- 待办:P4 同步自己的 star 历史(需要 token)。
