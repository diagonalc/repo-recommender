#!/usr/bin/env python3
"""P5:FastAPI 后端 —— 把库里的数据通过 HTTP 接口暴露出去。

启动:
    .venv/bin/uvicorn api:app --reload --port 8000

然后浏览器打开 http://127.0.0.1:8000/docs
—— 这是 FastAPI 白送的交互式文档,每个接口都能当场点着试,不用写 curl。
"""
import heapq
import json

from fastapi import FastAPI, HTTPException
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
def list_repos(sort: str = "stars", lang: str = None, limit: int = 30):
    """榜单。

    sort=stars    按总星数排(候选池全貌)
    sort=trending 按最近两个快照日之间的 star 增量排(要至少两份快照)
    """
    limit = max(1, min(limit, 200))
    conn = db.get_conn()

    if sort == "trending":
        dates = db.snapshot_dates(conn)
        if len(dates) < 2:
            raise HTTPException(
                status_code=409,
                detail="库里还只有一份快照,算不出增速;等 daily_update 再跑一天")
        rows = db.growth_rows(conn, dates[0], dates[1])
        items = [dict(r) for r in rows if not lang or r["language"] == lang]
        top = heapq.nlargest(limit, items, key=lambda r: r["delta"])
        attach_intros(conn, top)          # 这条分支也要补介绍(之前漏了)
        return {"sort": "trending", "since": dates[1], "as_of": dates[0],
                "count": len(top), "items": top}

    rows = db.list_by_stars(conn, lang=lang, limit=limit)
    items = [row_to_repo(r) for r in rows]
    attach_intros(conn, items)
    return {"sort": "stars", "lang": lang, "count": len(items), "items": items}


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
    out["intro"] = extract_intro(readme, out.get("description") or "", full_name)
    out["readme"] = readable(readme)          # 详情页直接展示这段,不再靠猜
    out["history"] = [dict(h) for h in db.repo_history(conn, rid)]
    out["delta"] = db.repo_delta(conn, rid)
    out["starred_at"] = db.starred_at_of(conn, rid)
    out["opinion"] = db.latest_opinions(conn).get(rid)
    out["similar"] = _similar_items(conn, rid)

    return out


@app.get("/api/me/starred")
def my_starred(limit: int = 200):
    """我 star 过的 repo,按 star 时间倒序 —— 这就是推荐系统的"口味来源"。"""
    conn = db.get_conn()
    rows = db.starred_list(conn, limit=max(1, min(limit, 1000)))
    items = [dict(r) for r in rows]
    attach_intros(conn, items)
    return {"count": len(items), "items": items}


@app.get("/api/recommend")
def api_recommend(limit: int = 20):
    """P6:内容相似推荐。

    这里用函数内 import(而不是文件顶部):sklearn 加载要好几秒,
    放顶部的话服务一启动就得等它,而 /api/repos 这些接口根本用不着它。
    """
    from recommend import recommend_for
    conn = db.get_conn()
    try:
        items = recommend_for(conn, max(1, min(limit, 100)))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"count": len(items), "items": items}


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
