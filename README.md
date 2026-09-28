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

### 环境:没有 sudo 也把环境搭起来了
- venv 是这么建的:`python3 -m venv --without-pip .venv`(绕开缺 ensurepip 的报错),
  再用官方 get-pip.py 往 venv 里塞 pip。全程不需要 sudo,也不用动系统 Python。
- token 放 `~/.config/repo-recommender/token`(在仓库外,不可能被提交)。
  找 token 的顺序:环境变量 GITHUB_TOKEN → 该文件。定时任务没有 shell 环境变量,
  所以文件这条路是必需的。

### P4 同步自己的 star 历史 —— 完成(2026-09-29)
- 学会:状态表 vs 流水表 —— starred 是"状态"(一个 repo 一行,重复同步只覆盖),events 是"流水"(只追加,同一条可以发生很多次)。建表方式完全不同,这是数据建模的第一课。
- 学会:/user/starred 的媒体类型 `Accept: application/vnd.github.star+json`。**带它才会返回 starred_at 真实 star 时间** —— ROADMAP 里写的"star 时间 GitHub 不给你,要用快照推算"是过时的,不用绕那个弯。下次核对文档,别信笔记。
- 结果:starred 15 行(带真实时间)、events 表带 CHECK 约束、sync_stars.py。

### P5 后端 API(FastAPI)—— 完成
- 学会:路由/路径参数/查询参数、Pydantic 请求体(自动校验 + 自动 422)、FastAPI 白送的 /docs、CORS 为什么必须开、`:path` 路径参数(因为 full_name 自带斜杠)。
- 接口:GET /api/repos(sort=stars|trending)、GET /api/repos/{owner}/{repo}(含快照历史)、GET /api/me/starred、POST /api/events、GET /api/events、GET /api/recommend。
- 实测 9 项全过,含错误分支(非法 action → 422、不存在的 repo → 404、只有一份快照时 trending → 409)。

### P6 内容相似推荐 —— 完成(README 全量抓完后可再提升)
- 学会:TF-IDF 直觉(词频 × 逆文档频率:自己文档里多 = 有代表性,所有文档里都多 = 区分不了任何东西)、为什么必须用稀疏矩阵(本库稀疏度 0.6%)、L2 归一化后"点积 = 余弦相似度"、jieba 处理中文、技术词(c++/node.js)不能被切碎。
- 结果:fetch_readmes.py(抓 README 当文本素材)、features.py(建向量并缓存)、similar.py(相似查询)、recommend.py(推荐 + 可解释的"因为你 star 过 X")。命令行和 HTTP 接口共用同一份逻辑,SQL 也挪到 db.py 避免两处各写一份。
- 效果:yt-dlp → youtube-dl / omniget(全对);推荐里出现 `niri-wm/niri`(因为你 star 了 niri 配置仓库)、`Clash-for-Windows_Chinese`(因为 clash-verge-rev)。
- 待改进:目前只有 137 个 repo 有 README,抓完 1265 个后重跑 `features.py` 质量会明显变好。

### P7 协同过滤 —— 有意跳过(ROADMAP 里本来就标"可选")
- 原因:它要"别人的行为数据"(采样高 star 用户的 star 列表 / GH Archive 子集),数据量和复杂度都上一个台阶;而且单用户、star 只有 15 个的场景下,P6 的内容相似已经够用。
- 想做的话:P6 的输出是干净的一层,再加一层协同过滤权重混进去即可,不用推倒重来。

### P8 前端网页 —— 完成
- 学会:fetch 调 API、DOM 构建节点(**用 textContent 而不是 innerHTML** —— repo 描述是别人写的文本,拼进 innerHTML 等于把别人的内容当代码执行)、tab 切换、卡片布局。
- 结果:web/index.html + web/app.js(原生 JS,无框架)。三个 tab:Trending / 推荐 / 我的;卡片有名称、描述、语言色点、star 数、topic 标签;[感兴趣]/[不感兴趣] 按钮 POST 到 /api/events —— **行为闭环打通**。
- 打开方式:后端 `uvicorn api:app --port 8000`,前端 `cd web && python3 -m http.server 5500`,然后浏览器访问 http://127.0.0.1:5500/

### P9 部署 —— 部分完成
- 已完成:每日自动更新(Windows 任务计划 → WSL → daily_update.py),日志在 logs/daily.log。
- 未做:公网部署、每天推送到手机。单机自用已经够,想上公网再学 Docker + 服务器。

### 后续增强(2026-09-29)
- **反馈可以改答案了**:以前点完就锁死,现在点另一个选项就能改。实现的关键是分清"流水"和"状态":events 表还是只追加(历史留全),但"当前态度"取每个 repo 的**最新一条**(`db.latest_opinions`)。所以改主意不会抹掉历史,而推荐永远跟着你最新的选择走。
- **"感兴趣"终于被推荐用上了**:之前 recommend.py 只用 not_interested 做排除,interested 点了等于白点。现在正向信号 = star 过的 ∪ 点过感兴趣的,负向信号 = 当前态度为不感兴趣(排除)。每条的推荐理由也说实话了 —— 分清"因为你 star 过 X"和"因为你点过感兴趣 X"(以前一律写"star 过",是错的)。
- **每条 repo 加了"介绍"**:从 README 里抽一段比 description 更具体的说明(intro.py)。这是启发式的,没有用模型,所以:
  - 实测 65% 能从 README 抽到正文,35% 退回 description
  - 抽到的里面大约一半质量好、一半带噪音(广告横幅、语言选择器、代码块)
  - 兜底策略是"拿不准就退回 description" —— 短一点,但一定是对的,不会把广告当介绍
  - **想根治得上模型做摘要**,那需要 API key
- 抽取的判据演进:先按"第一句不是噪音的"取 → 广告一直钻空子 → 改成"在候选句里挑和 description 词重合度最高的",重合度低于 0.25 就宁可退回 description。
