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

### 第三轮增强(2026-09-29 夜):标签 / 排序 / 刷新 / 详情页
- **详情页**:点任意 repo 名字进入,展示 README 正文、star 快照柱状图、相似 repo(可继续点进去)、以及可改的反馈按钮。接口一次给齐所有数据,不让前端连发好几个请求。标题不再直接跳 GitHub —— 想跳就在详情页点明确的按钮。
- **修掉两个 bug**:① `recommend_for` 没返回 `html_url`,导致推荐页的标题链接是坏的 ② `trending` 分支漏调 `attach_intros`(这个漏过一次,现在统一收到 `attach_extras` 里,避免再漏)。
- **排序**:`sort=trending|stars|pushed|name`,可以和标签筛选叠加。SORTS 集中在 db.py 一处,加新排序只改那里。
- **刷新**:右上角按钮重新拉当前列表(连同反馈状态)。
- **标签**:
  - 用 GitHub 自带的 **topics** 当标签 —— 作者自己选的,质量比瞎猜的关键词高。卡片上可点,点了看同标签的所有 repo;新增「标签」页做标签云。
  - 筛选用 SQLite 的 `json_each` 展开 JSON 数组来精确比对,**不能用 `LIKE '%"go"%'`** —— 那样 `django` 会被 `go` 误伤。
  - **自动补全**:169 个作者没设 topics 的 repo,用「语言 + 描述/README 的 TF-IDF 关键词」自动补标签,实现 1265/1265 全覆盖。
  - **自动标签单独存 `auto_tags` 表,绝不写回 `repos.topics`** —— 因为每天的 daily_update 会用 GitHub 返回的 topics 覆盖那一列,而 GitHub 对没设 topics 的仓库永远返回空数组,写回去第二天就被抹掉。要活得久的数据,得和自己的来源分开存。
  - 自动标签的质量:过滤掉了所有者名(README 里满篇都是)、版本号数字、赞助平台(patreon/tidelift 之类),但仍有残余噪音 —— 这是启发式的固有上限,已知可接受。

### 第四轮(2026-09-29 凌晨):换一批 / 作者头像 / 中英切换
- **"刷新"改成"换一批"**:第一版把刷新做成了"重新拉同一批",这是错的 —— 推荐是按分数排好的长列表,**重算一遍必然得到同样的排序,等于没换**。改成按 offset 往后翻一段,每次 30 个全新 repo,翻到最后自动回到第一批。实测四批两两零重叠。
- **作者 + 头像**:头像直接用 `https://github.com/<用户名>.png` 这个现成入口(会自动跳到头像图)。**不用存 avatar_url、不用回填 1265 行、不消耗 API 额度**。作者名可点,去 GitHub 主页。
- **界面中英切换**:所有文案抽进 `I18N` 表,用 `t("key")` 取。写死字符串的话,加一种语言就得满文件找,迟早漏几个。选择存在 localStorage,刷新后保持。
- **README 全量重抓完成 + 向量重建**:1264/1265 成功;词表 10719 → **14471 词**(README 正文的完整内容进来了),相似推荐随之变准。

### 第五轮(2026-09-29 凌晨):搜索 / 多标签 / 修 3 个 bug
- **bug:推荐页不显示标签**。`recommend_for` 的输出字典里根本没带 `topics` 字段(和之前漏 `html_url` 是同一类错误)。补上后,又发现第二层问题:推荐页只带作者 topics、没并自动标签,导致同一个 repo 在 Trending 页有标签、到推荐页没标签。**同一个字段两处口径不一致,最容易被当成 bug** —— 现在两处都走合并后的结果。
- **bug:卡片介绍块参差不齐**。原来是"抽到 README 介绍才显示那一块",于是有的卡有一块、有的没有,看着高低不齐。改成**每张卡恒定一块**:抽到就用 README 的,没抽到就用 description 兜底,描述行只在和这块内容不同时才单独显示。
- **bug:标签筛选的交互**。原来筛选条上是 `标签:agents ✕ 取消`,✕ 还套在标签里。改成:**只列标签本身、没有取消按钮,点标签自己就移除**。
- **新功能:多标签叠加筛选**。标签之间是**「与」**关系 —— 每多选一个收窄一次(实测 rust → 5 个,rust+cli → 5 个,rust+cli+ai → 3 个,结果都验过确实同时带这三个)。卡片上已选中的标签会高亮,再点一下取消。
- **新功能:搜索**。`GET /api/search?q=`,名字 / 描述 / 标签 / README 全文 / 自动标签都搜。排序按**命中位置分级**:名字命中 > 描述 > 标签 > README。不分级的话,一个只在 README 里顺带提了一句的 repo 会和名字直接命中的混在一起,最相关的反而要翻半天。中文也能搜(实测"语音"能搜到中文项目)。

### 第六轮(2026-09-29 凌晨):全站搜索 / 修 2 个交互问题
- **修 bug:取消完标签后跳错页**。原来标签清空会甩到"标签云",但用户的意图是"筛完了,回去接着看"。现在记住进标签页之前在哪一页(`state.returnTab`),清空后回到那儿。
- **优化:"换一批"从右上角挪到首行工具栏**。原来它在右上角,还要靠一句"点右上角换一批"的文字提示去指路 —— 按钮本身就该在那儿。右上角那个恢复成纯粹的"刷新"。
- **新功能:全 GitHub 搜索**。搜索框旁加了范围选择:`本地库` / `全 GitHub`。
  - 全站搜索走 GitHub 的 search 接口(`gh_search.py`),和 fetch_repos 用的是同一个接口,区别是一个是日常采集、一个是即时查询。
  - **结果会 upsert 进本地库** —— 不写进去的话结果只能看不能用:点名字进不了详情页、点"感兴趣"会 404。写进去之后它们和库里的 repo 完全一样。代价是候选池会随搜索变大(这是好事)。
  - **按需抓 README**:全站搜索刚并入的 repo 还没有 README,详情页会显示"没抓到",看着像坏了。所以详情接口在发现"没抓过"时会现抓一次并缓存。注意区分"没抓过"(没有行)和"抓过但确实没有 README"(存了空字符串)—— 后者不该重查。
  - 实测:`terminal file manager` → yazi / superfile / nnn / lf / fff;`中文 分词` → funNLP / jieba / pkuseg / ansj_seg。
