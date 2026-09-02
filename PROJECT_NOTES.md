# 项目对话纪要 / PROJECT NOTES

本文件汇总了 2026-09-02 关于本项目的对话要点,方便跨对话接续。
详细的分阶段学习+开发计划见 ROADMAP.md(那是主文件,本文件是背景与共识)。

---

## 1. 项目是什么

做一个"像视频网站一样"的 GitHub 仓库推荐工具:
记录用户(目前只有作者自己)的 star / 浏览 / 感兴趣等行为,
每天推荐"trending 且对口味的 repo"。
类比:抖音/B站 的内容流推荐,换成 repo 流。

参考的同类产品:libraries.io、givemegit、GitHub 自己的 For You、trending 导航站。

## 2. 项目背景

- 用户现状:刚学完数据结构 + OS 基础,Web 方向基本空白。
  是边学边做的学习型项目,不是纯工程交付。
- 学习原则(对话中确认):动手到哪学到哪(just-in-time),不先囤知识。
- 中文交流;开发机是 Arch Linux + niri(Wayland),终端是 kitty。
- 网络:直连日本/多数网站 OK;有 Clash Verge(mihomo 代理 127.0.0.1:7897),
  需要时可用(抓 GitHub 数据大概率直连即可,GitHub API 无需代理)。

## 3. 对话中确定的关键判断(背景知识,供接续参考)

数据侧:
- GitHub 没有官方 trending API → 用 GH Archive(每小时公开事件流)统计
  近 24h star 增量做增速榜,或解析 github.com/trending 页面。
- repo 元数据用 GitHub REST API(search 接口,分页,认证后限流 5000/时)。
- 协同过滤的"他人行为"数据:采样高 star 用户的公开 star 列表,
  或 GH Archive 子集。libraries.io 数据集是备选。
- 用户自己的口味信号:OAuth 后拉 /user/starred 最干净;
  单用户项目可简化:脚本定期拉自己的 star 列表即可,不一定要埋点。

推荐算法阶梯(从简到繁,分阶段上):
1. 冷启动:trending 榜 × 语言/topic 过滤
2. 内容相似:repo 向量化(README 用 TF-IDF/BM25 或 embedding),算余弦相似度
3. 协同过滤:item-based("star 过 A 的人也 star 了 B")/ implicit ALS
4. 混合:个性化分 × 新鲜度分 × 多样性,推送位留 10-20% 给探索(防信息茧房)

架构 MVP:
  采集定时任务 → Postgres/SQLite + Redis(可选)→ 离线算向量/模型 →
  推荐服务 API → 前端卡片流 → 行为埋点回流,形成闭环。
  单机即可,不需要 Kafka/Spark/Docker(用户阶段,别上重型组件)。

## 4. 已定稿的技术栈与路线(与 ROADMAP.md 一致)

Python + SQLite + FastAPI + scikit-learn(TF-IDF)+ 原生 HTML/JS。
全部免费、单机可跑、零 Docker 依赖。
分 P0-P9 十个阶段,预计 6-9 周(每天 1-2 小时)。
P7 协同过滤标为"可选进阶",做不出不丢人;P9 部署可选。

进度总览(里程碑):
  P0 环境+Git 仓库上线
  P1 GitHub API 采集 1000 repo
  P2 SQLite 入库可查询
  P3 增量快照 + 增速榜(第一个"能看的榜单")
  P4 同步自己的 star 历史
  P5 FastAPI 后端接口 /docs 全通
  P6 内容相似推荐(第一个真推荐)
  P7 协同过滤(可选)
  P8 前端网页,行为闭环
  P9 常驻 + 每日自动推送(可接 Hermes cron)

## 5. 协作约定(跨对话接续的关键)

- 用户进度记录在 repo-recommender/README.md(每阶段结束写 3 行:
  学会了什么 / 卡在哪 / 下一步)。
- 用户报"我在 P几 的哪一步"即可无缝接续上下文。
- 教/帮用户时的原则:
  * 先大白话+例子讲概念,再谈代码
  * 让用户复述确认理解,错了纠正
  * 出小改动练习题,别一次甩完整大功能
  * 报错让用户先自己读 30 秒
- 每个新概念让 AI 做三件事:讲概念(不给完整代码)→ 用户复述 → 出 3 道小题。

## 6. 当前状态

- 尚未开工(对话结束时停在"从 P0 开始?")。
- 项目目录 ~/repo-recommender/ 已建,内有本文件与 ROADMAP.md。
- 下一步:P0 —— venv + git init + README.md + 首次 commit/push。

## 7. 其他对话遗留事项(与本项目无关,备忘)

- 用户机器缺图形看图软件(在用 kitty + niri),曾建议装 imv
  (sudo pacman -S imv),未执行,用户未回复确认。
- K-ON 壁纸已下载到 ~/Pictures/k-on-wallpapers/(10 张),来源
  animekabegami.com,官方版权绘图。
