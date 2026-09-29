# 项目总览 / PROJECT OVERVIEW

> 写于 2026-09-29。这份文档是**从一个时间点给整个项目拍的照片** ——
> 讲清楚"现在有哪些东西、它们怎么连起来"。
> 详细的进度和踩坑记录在 README.md,最初的路线图在 ROADMAP.md,项目背景在 PROJECT_NOTES.md。

---

## 一、这个项目是什么

**一个"像视频网站一样"的 GitHub 仓库推荐器。**

记录你对仓库的行为(star、感兴趣 / 不感兴趣),每天给你推"在涨 + 对口味"的 repo。
和抖音的区别只是:内容从短视频换成了 repo。

参考过的同类产品:libraries.io、givemegit、GitHub 自己的 For You、trending 导航站。

---

## 二、整体结构:数据从哪来,到哪去

```
                    GitHub API
                        │
   ┌────────────────────┼────────────────────┐
   │                    │                    │
   ①每天自动            ②偶尔手动            ③登录后
   拉 repo 榜单          抓 README           同步你自己的
   │                    │                    │
   ▼                    ▼                    ▼
 repos 表            readmes 表          starred 表
 repo_snapshots 表                       following 表
   │                    │                    │
   │ 算增速              │ 算文本向量          │
   ▼                    ▼                    │
 trending 榜单        TF-IDF 向量             │
                        │                    │
                        └────► 推荐算法 ◄─────┘
                                  │          + events 表
                                  ▼          (你点的感兴趣)
                            api.py(HTTP 接口)
                                  │
                                  ▼
                            浏览器里的界面
```

**全部数据存在一个文件里:`data/repos.db`(SQLite)。**

---

## 三、文件清单(24 个文件,约 4900 行)

### 数据管道(后台跑,不面向用户)

| 文件 | 干什么 |
|---|---|
| `fetch_repos.py` | **P1**:调 GitHub 搜索接口批量拉 repo。含分页、限流退避、断点续跑 |
| `load_raw.py` | **P2**:把拉下来的原始 JSON 灌进数据库 |
| `daily_update.py` | **P3**:每天跑一次 —— 刷新元数据 + 记录当天 star 数快照 |
| `trending.py` | **P3**:对比两次快照,算"涨得最快"的榜 |
| `fetch_readmes.py` | **P6**:抓 README 原文(算相似度要用的文本素材) |
| `sync_stars.py` | **P4**:同步某个用户 star 过的仓库 |
| `sync_following.py` | 同步某个用户关注的开发者 |
| `autotag.py` | 给"作者没设标签"的仓库自动补标签 |
| `gh_search.py` | 全站搜索(即时查 GitHub,不是查本地库) |

### 数据层

| 文件 | 干什么 |
|---|---|
| `schema.sql` | **表结构** —— 描述"一个全新的数据库该长什么样" |
| `db.py` | **所有数据库操作 + 升级迁移**。别的脚本一律 import 它,不自己拼 SQL |

> `db.py` 里那堆 `_migrate_*` 函数是**升级老数据库用的**。
> 因为 SQLite 改不了主键和约束,只能"重建表 + 搬数据"。
> 每次启动服务它都会检查一遍"现在是什么版本、要不要升级"。

### 推荐算法(离线算,不接 HTTP)

| 文件 | 干什么 |
|---|---|
| `features.py` | 把每个 repo 的文字变成 **TF-IDF 向量**(数字化的"主题指纹") |
| `similar.py` | 给一个 repo,找最像它的几个 |
| `recommend.py` | **给一个用户**生成推荐列表(用他的 star + 感兴趣当口味信号) |
| `intro.py` | 从 README 里抽一段当"介绍"(纯启发式,不是 AI) |

### 后端

| 文件 | 干什么 |
|---|---|
| `api.py` | **FastAPI** —— 所有 HTTP 接口,顺便托管前端网页 |
| `auth.py` | **GitHub OAuth 登录**流程 |

### 前端

| 文件 | 干什么 |
|---|---|
| `web/index.html` | 页面骨架 + 全部样式 |
| `web/app.js` | 全部交互逻辑(1481 行,是最大的一个文件) |

### 入口脚本和文档

| 文件 | 干什么 |
|---|---|
| `run_server.sh` | 启动网站服务(端口写在这里) |
| `run_daily.sh` | 每天定时任务的入口 |
| `README.md` | 进度记录 + 踩过的坑 |
| `ROADMAP.md` | 最初的 P0-P9 学习路线 |
| `PROJECT_NOTES.md` | 项目背景和共识 |

---

## 四、数据库里现在有什么

```
repos             1353   ← 候选池:1353 个仓库
repo_snapshots    2424   ← 每个仓库每天的 star 数(存了 2 天)
readmes           1266   ← 抓到的 README
auto_tags          675   ← 自动补的标签
starred             15   ← 你 star 过的
following            8   ← 你关注的开发者
events              25   ← 你点的感兴趣 / 不感兴趣
comments             1   ← 评论
users                1   ← 就你一个
sessions             1   ← 你当前的登录会话

标签覆盖:1318 / 1353 个仓库有标签
快照日期:2026-09-22、2026-09-28
```

**表结构分组:**

| 分组 | 表 | 说明 |
|---|---|---|
| 公共数据 | `repos`、`repo_snapshots`、`readmes`、`auto_tags` | 所有人共用一份(每天由定时任务更新) |
| 按人分开 | `starred`、`following`、`events`、`comments` | 每张表都有 `user_id`,按登录用户隔离 |
| 登录相关 | `users`、`sessions` | 用户身份 + 会话 |

---

## 五、三条"链路"

### 链路 A:每天自动跑(无人值守)

```
Windows 任务计划(每天 10:17)
   → repo-recommender-daily.bat
   → wsl.exe 启动 WSL
   → run_daily.sh
   → daily_update.py
   → fetch_repos 拉 12 页(6 种语言 × 2 页)
   → 写进 repos 表(更新)+ repo_snapshots(记今天的 star 数)
```

**这条链路被坑过**:最先是配在 WSL 里的 cron,**六天一次都没跑** ——
因为 WSL 不启动,cron 根本不存在。改成 Windows 任务计划才解决。

### 链路 B:用户访问

```
浏览器打开网页
   → api.py 查 SQLite
   → 返回 JSON
   → app.js 渲染成页面

点"感兴趣"
   → POST /api/events
   → 写进 events 表

(下次) 算推荐
   → recommend.py 读你的 starred + events
   → 用 TF-IDF 向量找相似的
   → 出结果
```

### 链路 C:登录

```
点"用 GitHub 登录"
   → /auth/login → 跳到 GitHub
   → 你点"授权"
   → GitHub 带 code 跳回 /auth/callback
   → 服务端用 code 换 access_token(这步要 client secret)
   → 用 token 拉你的资料
   → 建/找用户 → 发一个会话 cookie → 写进 sessions 表
```

---

## 六、那堆"网络折腾"到底是怎么回事

这部分最容易迷失,单独说。**它和代码完全无关** —— 只影响"别人能不能访问到你的网站"。

```
第一层问题:WSL 默认躲在 NAT 后面
   WSL 有个自己的内网 IP(172.x),局域网设备访问不到
   解决:开镜像网络模式(.wslconfig)→ WSL 直接共享 Windows 的网卡

第二层问题:Windows 防火墙拦着
   解决:加一条放行规则(限本地子网,因为这台机器在校园网上)

第三层问题:WSL 还有自己的防火墙
   Win11 的 Hyper-V Firewall,入站默认 Block
   解决:再加一条 Hyper-V 规则

第四层问题(没解决):本机访问自己有"捷径"
   Windows 访问自己的局域网 IP 时,内核抄近路,翻的是自己的 socket 表
   → 本机用主机名 / IP 连不上,只能用 127.0.0.1
   → 别人的设备完全正常
```

**最后那层没解决,但它只影响"你自己",不影响别人用。**
而且**上了公网之后这四层全部消失** —— 因为有了固定域名。

---

## 七、现在的状态

| | 状态 |
|---|---|
| 数据 | 1353 个仓库、1266 篇 README、2 天快照 |
| 推荐 | 能用(TF-IDF 内容相似) |
| 前端 | 完整(7 个页面 + 详情页 + 翻译 + 深浅色 + 中英切换) |
| 多用户 | 代码完成,**已登录成功** ✓ |
| 定时任务 | Windows 任务计划,每天 10:17 |
| 局域网访问 | 可以(手机验证过) |
| **公网** | **没做** |

**按最初的 P0-P9 路线算:**

```
P0-P6  ✅ 完成(环境 / 采集 / 存储 / 榜单 / 行为 / 后端 / 相似推荐)
P7     ⏭️ 有意跳过(协同过滤,roadmap 本来就标"可选")
P8     ✅ 完成(前端 + 行为闭环)
P9     ⏳ 部分(每日自动更新有了,公网部署没有)
```

另外还做了很多路线图里没有的:多用户登录、标签系统、全站搜索、白天模式、翻译、已关注页…

---

## 八、还没做的

1. **公网部署** —— 需要:服务器 + 域名 + HTTPS + systemd 常驻
2. **token 加密存储** —— **公网部署前必须做的一条**:现在用户的 GitHub token 是明文存库的
3. **定时同步用户的 star / 关注** —— `sync_stars.py` / `sync_following.py` 目前要手动跑,没加进定时任务
