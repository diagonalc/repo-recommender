# GitHub Repo 推荐系统 — 学习+开发路线图

目标:做一个"像视频网站一样"的 GitHub 仓库推荐:记录你的 star/浏览行为,
每天给你推 trending 且对口味的 repo。

现状:已会数据结构 + OS 基础,Web 方向是空白。
节奏:每天 1-2 小时,总计约 6-9 周。原则 = 动手到哪学到哪,别先囤知识。

贯穿全程的规矩:
- 每个阶段结束 git commit 一次,写清 commit message
- 每阶段结束在 README.md 写 3 行总结:学会了什么 / 卡在哪 / 下一步
- 报错先自己读 30 秒再问 AI;让 AI 讲思路和逐行解释,别让它直接甩整个功能

---

## P0 准备(1-2 天)
目标:环境就绪,学会把代码交给 Git 托管。

要知道:
- venv:python3 -m venv .venv && source .venv/bin/activate
- Git 最小集:init / add / commit / branch / remote add / push
- GitHub Personal Access Token 怎么创建(读公开数据不需要写权限,
  勾 public repo 只读即可;限流从 60/时 升到 5000/时)
- .gitignore 是什么(防止把 token/数据提交上去)

产出:
- 目录 ~/repo-recommender/ 建好,里面 README.md 写项目简介
- 第一个 commit 并 push 到 GitHub(顺便练习 git)

验收:
- git log 能看到 commit;push 后 GitHub 网页能看到仓库
- python3 -c "print('ok')" 在 venv 里跑通

坑:
- token 泄露 = 账号风险,永远别提交;忘了就写进 .gitignore

---

## P1 数据采集:调 GitHub API(约 1 周)
目标:能批量把 repo 数据拉到本地。

要知道(必懂):
- HTTP:GET、请求头(Accept / Authorization)、状态码(200/403/429)、JSON
- API 分页:每页最多 100 条,靠 Link header 或 page 参数翻页
- 限流:未认证 60 次/时,认证 5000 次/时;429/403 要退避等待
- Python:requests 库、for 循环、try/except、json.dump、time.sleep

产出:
- fetch_repos.py:按语言关键词拉 repo 列表,存原始 JSON 到 data/raw/
  每个 repo 至少留:id, full_name, description, language, topics,
  stargazers_count, pushed_at, html_url
- 脚本要能断点续跑(记录已拉到的页,避免重拉撞限流)

验收:
- 稳定拉 1000 个 repo 不报错、不撞限流
- data/raw/ 里有按语言/页数命名的 JSON 文件

坑:
- 403 rate limit 和 403 forbidden 不一样,先看响应体里的说明
- 别并发狂拉,先单线程睡 0.5s

---

## P2 存储层(3-5 天)
目标:数据进数据库,能查。

要知道:
- SQL 基础:CREATE TABLE / INSERT / SELECT / WHERE / ORDER BY / LIMIT
- 数据库选型:先 SQLite(零安装,一个文件),以后要并发再换 Postgres
- 主键、UNIQUE 约束(防止重复行)、参数化查询(防注入+引号坑)
- upsert 概念:INSERT OR REPLACE / ON CONFLICT(重复抓取时更新而非报错)

产出:
- schema.sql:repos 表(带 UNIQUE full_name)
- db.py:连接 + upsert 函数
- 把 P1 的数据灌进库里

验收:
- sqlite3 命令行能跑出:按 star 数排序的前 20 个 repo
- 重复运行入库脚本,行数不翻倍(幂等)

坑:
- SQL 字符串拼接引号会炸 —— 一律用 ? 占位参数
- pushed_at 是 ISO8601 带时区,先统一存 UTC

---

## P3 增量更新 + Trending 榜(3-5 天)
目标:第一个能看的榜单:"近 24h star 涨得最快的 repo"。

要知道:
- 定时任务:systemd timer 或 cron(OS 知识正好用上)
- 时间处理:datetime / UTC / timedelta
- 增速 = 快照对比:今天 star 数 - 昨天 star 数
- Top-K 用 heapq(你 DS 学过堆,这里实战)

产出:
- repo_snapshots 表:每天记录每个 repo 的 star 数快照
- daily_update.py:每天定时跑,更新 repo 元数据 + 写快照
- trending.py:算今日增速榜,输出 Top 30

验收:
- 连续跑两天,能算出增量榜
- 榜单和 github.com/trending 对照,重合度别太离谱(量级一致即可)
- 里程碑:P3 结束你有了"能看的榜单页"(先用命令行打印)

坑:
- 老 repo star 基数大,绝对增量天然占优 —— 新 repo 可以按增量/年龄加权
- 时区口径统一,别拿 UTC 和本地时间直接减

---

## P4 用户行为记录(约 1 周)
目标:知道"你喜欢什么" —— 推荐系统的口味数据源。

要知道:
- GitHub API 的 /user/starred 端点(拉你自己的 star 历史)
- 事件模型:一条行为 = (谁, 对哪个 repo, 什么动作, 什么时间)
- 简化:单用户项目,不用做注册登录,数据就是"你"

产出:
- starred 表 + sync_stars.py:全量同步你 star 过的 repo(增量更新)
- events 表 + 简单接口雏形:记录"感兴趣 / 不感兴趣"的手动反馈
  (接口可以 P5 再做,这里先把表建好)

验收:
- 数据库里能看到你真实的 star 历史,按时间排序
- 手动插一条"不感兴趣"事件能查出来

坑:
- /user/starred 也是分页的,同样要翻页
- star 时间 GitHub 不给你,只给 repo 元数据 —— 想算"最近口味变化"
  就用快照:第一次见到某 repo 的日期≈star 日期

---

## P5 后端 API(FastAPI)(约 1 周)
目标:数据通过 HTTP 接口"流"出来,网页/命令行都能调。

要知道:
- FastAPI 基础:路由、路径参数、查询参数、Pydantic 模型
- 自动文档:/docs 页面(FastAPI 白送)
- 数据库读写封装成函数
- CORS(网页跨端口调后端要开)

产出:
- GET /api/repos?sort=trending|stars&lang=xxx   榜单
- GET /api/repos/{full_name}                    详情
- GET /api/me/starred                            我的收藏
- POST /api/events                               记录反馈
- 前端雏形可以先不做,curl 能调通就算过

验收:
- 浏览器开 http://127.0.0.1:8000/docs,每个接口点一遍能通
- curl 能拿到 P3 的榜单 JSON

坑:
- Pydantic 模型字段名和数据库列名对不上是最常见的报错源
- 开发时用 uvicorn --reload,改代码自动重启

---

## P6 推荐 v1:内容相似(1-1.5 周)
目标:推荐"和你 star 过的 repo 长得像的 repo"。第一个真推荐。

要知道:
- 向量直觉 + 余弦相似度(补一点:点积、归一化,半天量)
- TF-IDF:词频 × 逆文档频率,把文本变成向量
  用 sklearn 现成的,不用手写
- 中文 repo 描述分词要 jieba(TF-IDF 对中文要分词才有效)

产出:
- features.py:把每个 repo 的 description+topics+README 摘要变成 TF-IDF 向量
- similar.py:输入一个 repo,输出 Top-N 相似 repo
- 推荐 = 你 star 过的 repo 的相似 repo 们,按相似度×热度排序,去重

验收:
- 拿你最熟的 3 个 repo 各测一次,推荐结果"确实像"
- 把"像/不像"记下来,作为调参依据

坑:
- README 先清洗:去 HTML 标签、限长(前 2000 字符够用)
- 全库 TF-IDF 内存大:可以先只对"高分 repo"算,或按语言分桶
- 冷启动:你 star 太少(<10)时结果不稳,先靠 P3 trending 顶上

---

## P7 推荐 v2:协同过滤(1.5-2 周,进阶,可选)
目标:推荐"和你品味相似的其他开发者 star 的 repo"。
这是视频网站推荐的精髓,但也是最难的一块,做不出来不丢人,可后补。

要知道:
- 协同过滤直觉:star 过 A 的人也 star 了 B
- 隐式反馈 ALS(implicit 库)或朴素 item-item 共现
- 数据来源(真实他人行为):
  a) 采样 N 千个高 star 用户的公开 star 列表(GitHub API,注意限流)
  b) GH Archive 公开事件流(数据巨大,先下某一天子集练手)
- 矩阵稀疏问题、冷启动(新 repo 没人碰过 → 退回 P6)

产出:
- 用"其他用户的行为"算 repo-repo 相似度
- 最终排序 = P6 内容相似 × P7 协同 × P3 新鲜度,三路加权混合
  权重做成配置,方便调

验收:
- 推荐里出现你完全没听过、但确实对口的 repo —— 这是成功标志
- 权重调参:记录几次 A/B 式自测(哪版你点得多)

坑:
- 采样用户时避开机器人号(star 数异常整齐的)
- 矩阵存稀疏格式,别用普通二维数组

---

## P8 前端网页(1.5 周)
目标:能看的界面 + 行为闭环(你看 → 点 → 推荐变好)。

要知道:
- HTML/CSS 基础:flex 布局、卡片样式
- JS 最小集:fetch 调 API、DOM 渲染列表、按钮 onclick
- 极简方案:单个 index.html + app.js,不学框架
  (想学框架再上 Next.js/Vue,别在 P8 同时学两样)

产出:
- 三个 tab:Trending / 推荐 / 我的
- repo 卡片:名称、描述、语言、star 数、topic 标签
  按钮:[感兴趣] [不感兴趣],点击 POST 到 /api/events
- 页面样式抄 GitHub 深色风即可,不用原创设计

验收:
- 你每天打开页面 → 看推荐 → 点反馈 → 第二天推荐有变化(闭环!)
- 里程碑:P8 结束 = 项目完整闭环,自己用得顺手

坑:
- 跨域报错先查后端 CORS
- fetch 默认不带 cookie/凭证,本地单机无所谓,但别养成坏习惯

---

## P9 打磨与部署(可选)
目标:常驻运行 + 省心。

- 用 systemd 把后端做成常驻服务,开机自启
- 每日推荐摘要:可以接 Hermes 的 cron 定时任务,每天早上把 Top 10
  推到你的 Telegram/终端
- 数据量大了/想公网部署,再学 Docker + 一台小服务器
- 想加功能:只看不 star 也算弱信号、按语言过滤、周报邮件

验收:
- 跑满一周:每天自动更新、推荐质量稳定、没有崩过

坑:
- 别一上来就学 Docker/K8s,本地能跑一周再说

---

## 总览

阶段 | 主题 | 时间 | 里程碑产出
P0  | 环境+Git | 1-2天 | 仓库上线
P1  | GitHub API 采集 | 1周 | 1000 个 repo 落盘
P2  | 数据库 | 3-5天 | 能查的 repos 表
P3  | 增量+Trending | 3-5天 | 第一个榜单(命令行)
P4  | 行为记录 | 1周 | 你的 star 历史入库
P5  | FastAPI 后端 | 1周 | /docs 里接口全通
P6  | 内容相似推荐 | 1-1.5周 | "像的 repo"推荐
P7  | 协同过滤(可选) | 1.5-2周 | 惊喜推荐出现
P8  | 前端网页 | 1.5周 | 完整闭环,自己天天用
P9  | 部署打磨(可选) | 不定 | 常驻自动推送

技术栈定稿:Python + SQLite(SQLAlchemy 可选)+ FastAPI + sklearn(TF-IDF)
+ 原生 HTML/JS。全部免费、单机可跑、不需要 Docker。

每个新概念出现时,让 AI 干三件事:
1. 用大白话+一个例子讲概念(别让它直接给代码)
2. 你复述一遍给它听,讲错它纠正
3. 让它出 3 道小改动的题(改字段名/加排序),你改完它检查
