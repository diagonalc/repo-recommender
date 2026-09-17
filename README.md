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
