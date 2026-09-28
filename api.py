#!/usr/bin/env python3
"""P5:FastAPI 后端 —— 把库里的数据通过 HTTP 接口暴露出去。

启动:
    .venv/bin/uvicorn api:app --reload --port 8000

然后浏览器打开 http://127.0.0.1:8000/docs
—— 这是 FastAPI 白送的交互式文档,每个接口都能当场点着试,不用写 curl。
"""
import heapq
import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db

app = FastAPI(title="Repo Recommender API", version="0.1.0")

# 前端(比如 127.0.0.1:5500)调后端(8000)算跨域,浏览器默认会拦掉。
# 本地单用户项目,直接全放开最省事;真要上公网必须收紧成具体域名。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def row_to_repo(row):
    """sqlite3.Row → 能直接转成 JSON 的 dict。

    topics 在库里存的是 JSON 字符串(如 "[\"cli\",\"rust\"]"),
    出接口前还原成真正的数组,前端才好直接用。
    """
    d = dict(row)
    if "topics" in d:
        try:
            d["topics"] = json.loads(d["topics"] or "[]")
        except (TypeError, ValueError):
            d["topics"] = []
    return d


def attach_intros(conn, items):
    """给一批 repo 补上 intro 字段(从 README 里抽的那段介绍)。

    放在接口层而不是存进库:这样以后改了抽取规则,立即生效,不用回填数据。
    代价是每次请求都要现抽 —— 对 30 条来说可以忽略。
    """
    from intro import extract_intro
    readmes = db.readmes_for(conn, [it["id"] for it in items if it.get("id")])
    for it in items:
        it["intro"] = extract_intro(
            readmes.get(it.get("id"), ""),
            it.get("description") or "",
            it.get("full_name") or "",
        )


def attach_tags(conn, items):
    """把自动补的标签并进 topics。

    标签有两个来源(作者设的 topics / 我们自动补的 auto_tags),
    但从前端看只有"标签"这一个概念 —— 合并这一步就该在接口层做完,
    不能让前端自己去关心某个标签是哪来的。
    """
    auto = db.auto_tags_for(conn, [it["id"] for it in items if it.get("id")])
    for it in items:
        topics = it.get("topics")
        if isinstance(topics, str):        # 增速榜那条分支给的是原始 JSON 字符串
            try:
                topics = json.loads(topics or "[]")
            except (TypeError, ValueError):
                topics = []
        merged = list(topics or [])
        for t in auto.get(it.get("id"), []):
            if t not in merged:
                merged.append(t)
        it["topics"] = merged


def attach_extras(conn, items):
    """列表项要补的附加字段:介绍 + 合并后的标签。一处调用,免得漏。"""
    attach_intros(conn, items)
    attach_tags(conn, items)


class EventIn(BaseModel):
    """POST /api/events 的请求体。

    声明成 Pydantic 模型的好处:字段缺失或类型不对,FastAPI 自动返回 422 并说明原因,
    不用自己写校验。这也是 FastAPI 最省事的地方。
    """
    full_name: str
    action: str


@app.get("/")
def root():
    return {"hint": "接口都在这儿:/docs", "endpoints": [
        "/api/repos?sort=stars|trending&lang=python",
        "/api/repos/{owner}/{repo}",
        "/api/me/starred",
        "POST /api/events",
    ]}


@app.get("/api/repos")
def list_repos(sort: str = "stars", lang: str = None,
               tag: list[str] = Query(default=None), limit: int = 30):
    """榜单 / 筛选。

    sort=stars    总星数(默认)
    sort=pushed   最近推送时间
    sort=name     名称
    sort=trending 最近两个快照日之间的 star 增量(需要至少两份快照)

    tag 可以给多个(?tag=a&tag=b),之间是「与」的关系 —— 每多选一个就收窄一次。
    lang 也可以叠加。
    """
    limit = max(1, min(limit, 200))
    tags = [x for x in (tag or []) if x]
    conn = db.get_conn()

    if sort == "trending":
        dates = db.snapshot_dates(conn)
        if len(dates) < 2:
            raise HTTPException(
                status_code=409,
                detail="库里还只有一份快照,算不出增速;等 daily_update 再跑一天")
        rows = db.growth_rows(conn, dates[0], dates[1])
        items = [dict(r) for r in rows if not lang or r["language"] == lang]
        # 先并上自动标签再筛,否则筛选口径和列表接口不一致
        attach_tags(conn, items)
        if tags:
            items = [it for it in items
                     if all(x in (it.get("topics") or []) for x in tags)]
        top = heapq.nlargest(limit, items, key=lambda r: r["delta"])
        attach_intros(conn, top)
        return {"sort": "trending", "lang": lang, "tags": tags,
                "since": dates[1], "as_of": dates[0],
                "count": len(top), "items": top}

    if sort not in db.SORTS:
        raise HTTPException(
            status_code=422,
            detail=f"sort 只能是 {sorted(db.SORTS) + ['trending']}")

    rows = db.list_repos(conn, sort=sort, lang=lang, tags=tags, limit=limit)
    items = [row_to_repo(r) for r in rows]
    attach_extras(conn, items)
    return {"sort": sort, "lang": lang, "tags": tags,
            "count": len(items), "items": items}


@app.get("/api/search")
def search(q: str, scope: str = "local", limit: int = 60):
    """搜索 repo。

    scope=local   只搜本地库(名字 / 描述 / 标签 / README),按命中位置分级排序
    scope=github  搜整个 GitHub,现查现用

    全站搜索的结果会并入本地 repos 表 —— 不写进去的话,结果只能看不能用:
    点名字进不了详情页(本地库没有)、点"感兴趣"会 404。
    写进去之后它们和库里的 repo 完全一样,代价是候选池会随搜索变大(这是好事)。
    """
    q = (q or "").strip()
    if not q:
        raise HTTPException(status_code=422, detail="搜索关键词不能为空")

    limit = max(1, min(limit, 100))
    conn = db.get_conn()

    if scope == "github":
        from gh_search import search_github
        try:
            raw = search_github(q, limit)
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))

        db.init_db(conn)
        db.upsert_repos(conn, raw)            # 并入本地库,后续操作才用得上
        rows = db.rows_by_full_names(conn, [r.get("full_name") for r in raw])
        items = [row_to_repo(r) for r in rows]

        # 保持 GitHub 返回的顺序(它已按 star 排好),别被数据库的返回顺序打乱
        order = {r.get("full_name"): i for i, r in enumerate(raw)}
        items.sort(key=lambda it: order.get(it["full_name"], 9999))

        attach_extras(conn, items)
        return {"q": q, "scope": "github", "count": len(items), "items": items}

    rows = db.search_repos(conn, q, limit)
    items = [row_to_repo(r) for r in rows]
    for it in items:
        it.pop("rank", None)          # 排序用的内部字段,不用给前端
    attach_extras(conn, items)
    return {"q": q, "scope": "local", "count": len(items), "items": items}


@app.get("/api/tags")
def list_tags(limit: int = 200):
    """所有标签 + 各自带多少个 repo。

    标签就是 GitHub 的 topics —— 它们是仓库作者自己选的,
    质量比我们瞎猜的关键词高得多,拿来当分类最省事。
    """
    conn = db.get_conn()
    rows = db.list_tags(conn, limit=max(1, min(limit, 500)))
    return {
        "count": len(rows),
        "tagged_repos": db.tag_cloud_count(conn),
        "total_repos": db.count_repos(conn),
        "items": [dict(r) for r in rows],
    }


def _similar_items(conn, repo_id, n=6):
    """和这个 repo 最像的几个。没建过向量缓存就返回空 —— 详情页不该因为这个 500。"""
    try:
        from features import load_features
        from similar import similar_rows
        matrix, ids = load_features()
    except SystemExit:
        return []

    sims = similar_rows(matrix, ids, repo_id, n)
    if not sims:
        return []

    marks = ",".join("?" * len(sims))
    meta = {r["id"]: (r["full_name"], r["language"], r["stargazers_count"])
            for r in conn.execute(
                f"SELECT id, full_name, language, stargazers_count FROM repos "
                f"WHERE id IN ({marks})", tuple(rid for rid, _ in sims))}
    return [{"full_name": meta[rid][0],
             "language": meta[rid][1],
             "stargazers_count": meta[rid][2],
             "similarity": round(score, 4)}
            for rid, score in sims if rid in meta]


def _fetch_readme_now(conn, repo_id, full_name):
    """按需抓一次 README 并缓存。

    抓不到就返回空串 —— 详情页的其他部分照常显示,不能因为 README 拉不到就打不开。
    """
    try:
        from fetch_readmes import clean, fetch_readme
        raw = fetch_readme(full_name)
    except (RuntimeError, OSError):
        return ""

    if raw is None:
        db.save_readme(conn, repo_id, "")      # 记一条空,下次不再重复查它
        return ""

    text = clean(raw)
    db.save_readme(conn, repo_id, text)
    return text


@app.get("/api/repos/{full_name:path}")
def repo_detail(full_name: str):
    """单个 repo 的详情页所需的全部数据。

    一次请求给齐:元数据 + README 正文 + 快照历史 + 我的态度 + 相似 repo。
    分成好几个接口让前端连发,既慢又难处理部分失败。

    full_name 形如 owner/repo,本身带斜杠,所以路径参数必须写 :path,
    否则 FastAPI 会把它当成两段路径。
    """
    conn = db.get_conn()
    row = db.get_repo(conn, full_name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"库里没有 {full_name}")

    rid = row["id"]
    out = row_to_repo(row)

    from intro import extract_intro, readable
    readme = db.repo_readme(conn, rid)

    # 还没抓过 README 就现抓一次并缓存。
    # 全站搜索刚并入的 repo 属于这种 —— 不补这一步,点进去就是"没抓到 README",
    # 看着像坏了。只抓一次,之后走缓存。
    if not readme and not db.has_readme_row(conn, rid):
        readme = _fetch_readme_now(conn, rid, full_name)
    out["intro"] = extract_intro(readme, out.get("description") or "", full_name)
    out["readme"] = readable(readme)          # 详情页直接展示这段,不再靠猜
    out["history"] = [dict(h) for h in db.repo_history(conn, rid)]
    out["delta"] = db.repo_delta(conn, rid)
    out["starred_at"] = db.starred_at_of(conn, rid)
    out["opinion"] = db.latest_opinions(conn).get(rid)
    out["similar"] = _similar_items(conn, rid)
    attach_tags(conn, [out])          # 详情页的标签也要含自动补的

    return out


@app.get("/api/me/starred")
def my_starred(limit: int = 200):
    """我 star 过的 repo,按 star 时间倒序 —— 这就是推荐系统的"口味来源"。"""
    conn = db.get_conn()
    rows = db.starred_list(conn, limit=max(1, min(limit, 1000)))
    items = [dict(r) for r in rows]
    attach_extras(conn, items)
    return {"count": len(items), "items": items}


@app.get("/api/recommend")
def api_recommend(limit: int = 20, offset: int = 0):
    """P6:内容相似推荐。

    offset 用来"换一批":推荐是按分数排好的一个长列表,把 offset 往后移
    就拿到新的一段,每次都是没看过的新 repo。
    (重算一遍是没用的 —— 同样的输入必然得到同样的排序,等于没换。)

    这里用函数内 import(而不是文件顶部):sklearn 加载要好几秒,
    放顶部的话服务一启动就得等它,而 /api/repos 这些接口根本用不着它。
    """
    from recommend import recommend_for

    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    conn = db.get_conn()
    try:
        items = recommend_for(conn, limit, offset)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {
        "count": len(items),
        "offset": offset,
        "has_more": len(items) == limit,      # 还有下一批可换
        "items": items,
    }


@app.post("/api/events", status_code=201)
def post_event(ev: EventIn):
    """记一条反馈。前端点 [感兴趣] / [不感兴趣] 就调这里。"""
    if ev.action not in db.EVENT_ACTIONS:
        raise HTTPException(status_code=422,
                            detail=f"action 只能是 {list(db.EVENT_ACTIONS)}")
    conn = db.get_conn()
    repo_id = db.find_repo_id(conn, ev.full_name)
    if repo_id is None:
        raise HTTPException(status_code=404,
                            detail=f"库里没有 {ev.full_name}")
    db.add_event(conn, repo_id, ev.action)
    return {"ok": True, "full_name": ev.full_name, "action": ev.action}


@app.get("/api/events")
def list_events(limit: int = 20):
    conn = db.get_conn()
    return {"items": [dict(r) for r in db.recent_events(conn, limit)]}


@app.get("/api/opinions")
def my_opinions():
    """{full_name: action} —— 每个 repo 当前的最终态度(最新一条事件说了算)。

    前端拿它给按钮标选中状态:这样你改过答案之后,刷新页面还能看出自己选的是哪个。
    """
    conn = db.get_conn()
    return {"opinions": db.opinion_map(conn)}
