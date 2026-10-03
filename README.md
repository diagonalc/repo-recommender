# Observatory

[![Ask DeepWiki](./web/badge.svg)](https://deepwiki.com/diagonalc/repo-recommender)
<!-- ↑ 用的是**仓库里自己那份** web/badge.svg,不直连 deepwiki.com。

     为什么不能直连(原来写的是 `https://deepwiki.com/badge.svg`):
     deepwiki.com 前面挡着 Vercel 的机器人风控,对非浏览器请求一律回
     429 + 一个"请完成验证"的 HTML 页面 —— 而 **<img> 标签跑不了 JS,过不去验证**;
     GitHub 渲染外链图片走的也是它自己的代理,一样过不去。
     (实测:不走代理 / 装成浏览器 / 连试三次,全是 429;shields.io 对照是 200。)
     所以官方 SVG 是**用浏览器打开、过了验证之后另存的**,放进了仓库 ——
     这样跟着仓库走,不求人,也不受那边风控影响。 -->


记录你 star 过什么、对什么感兴趣,每天从"正在涨"的仓库里挑出对你口味的推给你。

> 线上:https://diagonalc.dpdns.org
>
> 架构详解看 [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) ·
> 开发过程中的决策与踩坑看 [DEVLOG.md](DEVLOG.md) ·
> 部署运维看 [DEPLOY.md](DEPLOY.md)

---

## 能做什么

**推荐**
- 「为你推荐」—— 拿你 star 过的 + 点过感兴趣的当口味信号,用 TF-IDF 找**内容相似**的仓库
- **star 比"感兴趣"重**(1.0 : 0.5)—— star 是主动收藏,随手点一下的心意没那么重
- 每条都写清理由(`★ 因为你 star 过 X` / `♥ 因为你点过感兴趣 X`)
- **每 10 个位置留 1 个"换换口味"** —— 挑一个不像你、但很多人用或最近在涨的仓库。
  只按相似度排会越推越窄,最后整页都是同一类东西的变体(信息茧房)
- 排序可切成:相似度 / star 数 / 名称;滚到底自动加载下一批

**发现**
- 「Trending」—— 按相邻两次快照之间的 **star 增量**排的增速榜
- 标签多选筛选(之间是「与」关系)、按语言筛
- 「标签」页有 **标签搜索**(按标签名筛,冷门标签也搜得到)
- 搜索:**本地库**全文搜(名称 / 描述 / 标签 / README),或**全 GitHub** 实时搜;
  结果可**排序** —— 相关度 / star 数 / 名称 / 最近更新
- 详情页:README 全文、star 历史曲线、相似仓库、评论区

**个人**
- 已收藏 / 已关注(GitHub OAuth 登录后从你自己的账号同步)
- **已收藏 → 现状** —— 换个角度看你 star 过的东西:还在更新吗、还在涨吗

**分站:兔子洞**
- 一个独立的小站
- 名单由关键词从整个 GitHub 搜出来(见 `fetch_acg.py`),**有自己的配色**
- 竖栏第一项是「返回主站」;洞里有**列表**(搜索 / 排序 / 按标签筛)和**标签云**
- 搜索和标签**只在这份名单里**(4608 个),不会把主站那几万个仓库捞进来
- 详情页和主站**共用** —— 同一份数据没必要做两遍
- 感兴趣 / 不感兴趣,点错了能改
- 介绍和 README 都能翻译成中 / 英

**其他**
- 深色 / 浅色模式、中英界面切换、手机可用
- **多用户**:每个人有自己的收藏、关注、反馈和推荐

---

## 快速开始（开发者）

```bash
cd ~/repo-recommender

# 首次:虚拟环境 + 依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 准备数据(第一次必须跑,顺序别换 —— 后面依赖前面的产物)
.venv/bin/python daily_update.py     # 拉仓库元数据 + 记今天的 star 快照
.venv/bin/python fetch_readmes.py    # 抓 README(推荐质量基本靠它)
.venv/bin/python features.py         # 把仓库文字变成 TF-IDF 向量

# 起服务
bash run_server.sh                   # 默认 http://127.0.0.1:18080/
```

### 可选:配 GitHub 登录

不配也能浏览,但**没有推荐** —— 推荐需要你的 star 数据当口味信号。

1. 在 https://github.com/settings/developers 建一个 OAuth App,
   回调地址填 `<你的地址>/auth/callback`
2. 写凭据:

```bash
mkdir -p ~/.config/repo-recommender
cat > ~/.config/repo-recommender/oauth.env <<'EOF'
REPOS_GH_CLIENT_ID=你的_client_id
REPOS_GH_CLIENT_SECRET=你的_client_secret
EOF
chmod 600 ~/.config/repo-recommender/oauth.env
```

### 可选:配 GitHub token(采集用)

不配的话采集会被限流到 10 次/分钟(配了 30 次/分钟),很容易整天拉不全:

```bash
printf '%s' 'ghp_xxx' > ~/.config/repo-recommender/token
chmod 600 ~/.config/repo-recommender/token
```

> ⚠️ `~/.config/repo-recommender/` 在**仓库之外**,技术上不可能被 git 提交。
> 永远不要把 token / client secret 写进任何会被提交的文件 —— 一旦推上 GitHub,
> 它会在几分钟内被爬虫拿去用。

---

## 项目结构

```
采集(离线跑)          db.py / schema.sql        接口(HTTP)          网页
─────────────         ───────────────          ───────────         ─────
fetch_repos.py  ─┐                             api.py      ─┐
daily_update.py ─┼─►  repos / snapshots  ─►    auth.py      ├─►  web/index.html
fetch_readmes.py─┤    readmes / auto_tags      recommend.py─┘    web/app.js
sync_stars.py   ─┘    starred / following
                      events / comments
```

| 文件 | 干什么 |
|---|---|
| `fetch_repos.py` | 调 GitHub 搜索接口批量拉仓库(分页 / 限流退避 / 断点续跑) |
| `daily_update.py` | 每天跑一次:刷新元数据 + 记当天 star 快照 |
| `fetch_readmes.py` | 抓 README 原文,算相似度的文本素材 |
| `autotag.py` | 给作者没设标签的仓库自动补标签 |
| `sync_stars.py` / `sync_following.py` | 同步**一个**用户的 star / 关注列表 |
| `sync_all.py` | 给**所有**登录过的用户跑上面两个 —— 每日任务调的就是它 |
| `sync_common.py` | 上面两个共用的分页取数和错误类型 |
| `gh_search.py` | 全 GitHub 实时搜索(和本地库搜索是两回事) |
| `fetch_acg.py` | **二次元分站**的采集:按关键词表从 GitHub 搜一批域名进 `acg_repos` |
| `db.py` | **所有数据库操作 + 升级迁移**。别的脚本一律 import 它,不自己拼 SQL |
| `schema.sql` | 表结构,描述"一个全新数据库该长什么样" |
| `features.py` | TF-IDF 向量化(内含一段暂时没接进产品的二维降维代码,见 DEVLOG 的"搁置的想法") |
| `recommend.py` / `similar.py` | 推荐算法 / 单个仓库的相似查询 |
| `intro.py` | 从 README 抽一段当"介绍"(启发式,不是 AI) |
| `trending.py` | 命令行版增速榜(和网页用的是同一份 SQL) |
| `api.py` | **FastAPI** —— 所有 HTTP 接口,顺便托管前端 |
| `auth.py` | GitHub OAuth 登录 |
| `ratelimit.py` | 按 IP 限流 —— 保护**共享的** GitHub / 翻译额度 |
| `backup_db.py` | 数据库备份(每天定时跑,保留最近 14 份) |
| `web/index.html` · `web/app.js` | 前端(原生 JS,无框架) |
| `run_server.sh` · `run_daily.sh` | 两个入口脚本,端口和时间只写在这里 |
| `RepoRecommenderDaily.xml` | Windows 任务计划的定义(定时采集) |
| `tests/` | 九个检查脚本,见下 |

---

## 测试

```bash
.venv/bin/python tests/check_frontend.py    # 前端:语法 + 中英文案对齐 + 死代码
.venv/bin/python tests/test_migration.py    # 数据库迁移可重入(中断后能自愈)
.venv/bin/python tests/test_fetch_retry.py  # 网络故障不能炸掉采集任务
.venv/bin/python tests/test_sync_all.py     # 同步:一人失败不拖累他人 + 退出码分类
.venv/bin/python tests/test_cookie_secure.py # cookie 的 Secure 标志算得对不对
.venv/bin/python tests/test_recommend.py    # 推荐:分页稳定 + 探索位 + 权重真的生效
.venv/bin/python tests/test_search_tags.py  # 标签搜索(冷门标签也搜得到)+ 搜索排序
.venv/bin/python tests/smoke_api.py         # 每个 HTTP 端点打一遍(需要服务在跑)
.venv/bin/python tests/check_no_leak.py     # 没有任何接口泄漏用户的 GitHub token(需要服务在跑)
```

这几个脚本都是**为了防住已经真实发生过的事故**(丢数据、接口 500、白屏、
token 泄漏),不是凑数的覆盖率。改完代码至少跑一遍。

需要解释器以外的东西:前端那个依赖 `esprima`(`pip install esprima`)——
这台机器没有 node,用它补上"改完 JS 没法检查语法"这一关。

---

## 运维

```bash
curl -s https://diagonalc.dpdns.org/api/health
# {"ok":true,"repos":1403,"snapshots":4825,"last_snapshot":"2026-10-02","stale_days":0}
```

**`stale_days` 是最值得盯的那个数** —— "最新快照距今天数"。
正常 ≤1;连着变大就意味着**每日任务挂了**,而页面完全看不出来
(老数据照样渲染,trending 照样出榜,只是数字不再变)。
这个项目已经栽过一次:连着两天没跑。

数据库每天自动备份一份到 `data/backups/`,保留最近 14 份:

```bash
.venv/bin/python backup_db.py --list     # 看有哪些
.venv/bin/python backup_db.py            # 手动再备一份
```

> 备份用的是 `sqlite3` 的 `backup()` 接口,**不是 `cp`** ——
> 库跑在 WAL 模式下,直接拷 `.db` 会得到一份缺了最新数据的备份,
> 而且它看起来完全正常。(第一次做备份就是这么错的。)

---

## 技术栈

Python + SQLite + FastAPI + scikit-learn(TF-IDF)+ 原生 HTML/JS。
零 Docker、零前端框架、全部免费、单机可跑。

---

## 已知限制

- **快照历史还很短**。trending 是"相邻两次快照相减",所以现在算出来的是**大约两三天**的增量,
  不是一周或一个月。快照每天攒一份,历史越长窗口越有意义。
- **GitHub token 明文存在数据库里**。给自己和朋友用没问题;真要对陌生人开放,
  得先把这一条解决掉。
- **候选池是"6 种语言 × star 前 1200 名"**。冷门仓库掉出这个范围就不再被更新。
- **SQLite 单文件**,并发写入会锁。当前规模(个位数用户)完全够,再大要换 Postgres。
- **介绍是从 README 抽的**,启发式,大约一半质量不错、一半带噪音;抽不准就退回 description。

---

## 文档

| 文档 | 内容 |
|---|---|
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | 架构详解:数据怎么流、三条链路、表结构 |
| [DEVLOG.md](DEVLOG.md) | 开发日志:P0-P9 每阶段的收获 + 22 轮迭代的决策与踩坑 |
| [DEPLOY.md](DEPLOY.md) | 部署运维:WSL 网络、防火墙、Cloudflare 隧道、定时任务 |
| [ROADMAP.md](ROADMAP.md) | 最初的 P0-P9 学习计划(已走完,留作学习记录) |
