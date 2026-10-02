#!/usr/bin/env python3
"""P5:FastAPI 后端 —— 把库里的数据通过 HTTP 接口暴露出去。

启动:
    .venv/bin/uvicorn api:app --reload --port 8000

然后浏览器打开 http://127.0.0.1:8000/docs
—— 这是 FastAPI 白送的交互式文档,每个接口都能当场点着试,不用写 curl。
"""
import heapq
import json
import os
import re
import time
from contextlib import asynccontextmanager

import requests

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import auth
import db

COOKIE = "repos_sid"        # 会话 cookie:登录后发,退出登录删
# 注:OAuth 的 state 以前也放 cookie,现在改成存服务端(见 db.save_state)。
# 手机浏览器策略、以及"从 127.0.0.1 发起登录但回调跳到公开域名"这两种情况,
# 都会让那个 cookie 送不回来,表现为登录时报"state 不匹配"。


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动时建表。schema.sql 里全是 IF NOT EXISTS,重复执行没副作用 ——
    # 但不加这一步,新加的表(比如 comments)要等别的脚本跑过才存在,
    # 直接调接口就会报"no such table"。
    db.init_db(db.get_conn())
    yield


app = FastAPI(title="Repo Recommender API", version="0.1.0", lifespan=lifespan)

# 前端(比如 127.0.0.1:5500)调后端(8000)算跨域,浏览器默认会拦掉。
# 本地单用户项目,直接全放开最省事;真要上公网必须收紧成具体域名。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def current_user(request: Request):
    """当前登录的人;没登录返回 None。"""
    conn = db.get_conn()
    return db.user_by_session(conn, request.cookies.get(COOKIE))


def require_user(request: Request):
    """要登录才能用的接口,先过这一道。"""
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


# ---------------- 登录 ----------------

@app.get("/auth/login")
def auth_login(request: Request):
    """跳去 GitHub 授权。"""
    if not auth.configured():
        raise HTTPException(
            status_code=503,
            detail="还没配置 OAuth 凭据。把 Client ID / Secret 填进 "
                   "~/.config/repo-recommender/oauth.env,然后重试")
    client_id, _ = auth.credentials()
    state = auth.new_state()
    # 回调地址必须和 GitHub OAuth App 里登记的一模一样,否则会被拒。
    # 注意别自己拼 —— 走 auth.redirect_uri() 统一处理反向代理那层
    # (隧道后面请求是 http,而用户看到的是 https,直接推会错)。
    redirect_uri = auth.redirect_uri(str(request.base_url))

    # state 记在**服务端**,不用 cookie(原因见 db.save_state 上面的注释)
    conn = db.get_conn()
    db.init_db(conn)
    db.save_state(conn, state)

    return RedirectResponse(auth.authorize_url(client_id, redirect_uri, state))


@app.get("/auth/callback")
def auth_callback(request: Request, code: str = None, state: str = None,
                  error: str = None):
    """GitHub 带 code 回到这里。"""
    if error:
        raise HTTPException(status_code=400, detail=f"GitHub 拒绝了登录:{error}")
    if not code:
        raise HTTPException(status_code=400, detail="没收到 code")

    conn = db.get_conn()
    db.init_db(conn)

    # state 必须是我们发出去过的(防 CSRF)。是就删掉,一条只能用一次。
    if not db.consume_state(conn, state):
        raise HTTPException(
            status_code=400,
            detail="这个登录链接无效或已过期 —— 回首页重新点一次登录")

    redirect_uri = auth.redirect_uri(str(request.base_url))
    try:
        token = auth.exchange_code(code, redirect_uri)
        gh = auth.fetch_user(token)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    user_id, _is_new = db.upsert_user(conn, gh)
    sid = db.create_session(conn, user_id)

    resp = RedirectResponse("/")
    resp.set_cookie(COOKIE, sid, httponly=True, samesite="lax",
                    max_age=60 * 60 * 24 * 30)   # 30 天
    return resp


@app.post("/auth/logout")
def auth_logout(request: Request):
    sid = request.cookies.get(COOKIE)
    if sid:
        db.delete_session(db.get_conn(), sid)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE)
    return resp


@app.get("/api/me")
def whoami(request: Request):
    """当前登录的是谁。没登录也返回 200(前端要靠它决定显示登录还是头像)。"""
    user = current_user(request)
    if user is None:
        return {"logged_in": False, "oauth_ready": auth.configured()}
    return {
        "logged_in": True,
        "user": {
            "login": user["login"],
            "name": user["name"],
            "avatar_url": user["avatar_url"],
            "html_url": f"https://github.com/{user['login']}",
        },
    }


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
    """列表项要补的附加字段:介绍 + 合并后的标签 + 评论数。一处调用,免得漏。"""
    attach_intros(conn, items)
    attach_tags(conn, items)

    counts = db.comment_counts(conn, [it["id"] for it in items if it.get("id")])
    for it in items:
        it["comment_count"] = counts.get(it.get("id"), 0)


class EventIn(BaseModel):
    """POST /api/events 的请求体。

    声明成 Pydantic 模型的好处:字段缺失或类型不对,FastAPI 自动返回 422 并说明原因,
    不用自己写校验。这也是 FastAPI 最省事的地方。
    """
    full_name: str
    action: str


# 注意:这里曾经有一个 @app.get("/") 返回接口清单 —— 删掉了。
# 它会挡住末尾挂载的静态文件,导致打开网站看到一坨 JSON 而不是页面。
# 接口清单在 /docs 里有,不用自己再写一个。


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
        # 增速查询里那列叫 stars(因为旁边还有 prev_stars),但其它接口和前端
        # 统一用 stargazers_count。**差一个字段名,卡片上就显示成"★ ?"** ——
        # 这类不一致特别难查:数据明明在,只是名字对不上。所以在出口处抹平。
        for it in top:
            it["stargazers_count"] = it.get("stars")
        attach_extras(conn, top)          # 用 attach_extras,别只调 attach_intros —— 会漏字段
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
def repo_detail(request: Request, full_name: str):
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
    # 详情页不强制登录,但"你 star 过没""你表过什么态"是个性化的 —— 登录了才有
    viewer = current_user(request)
    if viewer:
        out["starred_at"] = db.starred_at_of(conn, viewer["id"], rid)
        out["opinion"] = db.latest_opinions(conn, viewer["id"]).get(rid)
    else:
        out["starred_at"] = None
        out["opinion"] = None
    out["similar"] = _similar_items(conn, rid)
    out["releases_url"] = (out.get("html_url") or "").rstrip("/") + "/releases"
    # 笔记直接并进详情响应 —— 详情页一次请求拿齐,不用再发一次
    out["comments"] = [dict(c) for c in db.list_comments(conn, rid)]
    attach_tags(conn, [out])          # 详情页的标签也要含自动补的

    return out


class CommentIn(BaseModel):
    body: str


@app.post("/api/comments/{full_name:path}", status_code=201)
def post_comment(request: Request, full_name: str, c: CommentIn):
    """给某个 repo 写一条笔记。

    路径放在 /api/comments/ 而不是 /api/repos/... 下面:
    /api/repos/{full_name:path} 的路径参数是**贪婪**的,会把后面的 /comments
    一起当成仓库名吃掉。换个前缀,不用去赌路由注册顺序。

    返回更新后的整份列表,前端拿到就能直接重渲染,不用再查一次。
    """
    body = (c.body or "").strip()
    if not body:
        raise HTTPException(status_code=422, detail="内容不能为空")
    if len(body) > 2000:
        raise HTTPException(status_code=422, detail="内容太长(上限 2000 字)")

    conn = db.get_conn()
    repo_id = db.find_repo_id(conn, full_name)
    if repo_id is None:
        raise HTTPException(status_code=404, detail=f"库里没有 {full_name}")

    user = require_user(request)       # 评论要署名的,必须先知道你是谁
    db.add_comment(conn, user["id"], repo_id, body)
    return {"ok": True, "full_name": full_name,
            "items": [dict(r) for r in db.list_comments(conn, repo_id)]}


@app.post("/api/star/{full_name:path}")
def star_repo(request: Request, full_name: str):
    """真的去 GitHub 给这个 repo 点 star(不是本地标记)。

    **用登录者自己的 token** —— 多用户之后不能拿站长的 token 替所有人点星。
    """
    user = require_user(request)
    conn = db.get_conn()
    token = db.user_token(conn, user["id"])
    if not token:
        raise HTTPException(status_code=409,
                            detail="你的账号没有可用的 GitHub token,退出后重新登录一次")

    try:
        r = requests.put(
            f"https://api.github.com/user/starred/{full_name}",
            headers={"Authorization": f"token {token}",
                     "Accept": "application/vnd.github+json",
                     "Content-Length": "0"},
            timeout=30)
    except requests.RequestException as e:
        # 这里原来**完全没有 try** —— 代理一抖就是一个 500。
        # 用户看到光秃秃的 "Internal Server Error":既不知道是网络问题,
        # 也不知道该不该重试、更不知道该去查代理。
        # (2026-10-02 采集任务崩溃的就是同一类异常,那次丢了一整天数据。)
        raise HTTPException(
            status_code=502,
            detail=f"连不上 GitHub:{type(e).__name__}。检查代理是否正常,稍后再试")

    if r.status_code == 204:
        # 本地也记一笔,界面立刻能反映。以后跑 sync_stars 会用真实时间覆盖。
        repo_id = db.find_repo_id(conn, full_name)
        if repo_id:
            db.save_starred(conn, user["id"], [{"repo": {"id": repo_id},
                                                "starred_at": db.today_utc()}])
        return {"ok": True, "full_name": full_name}

    # 权限不足时 GitHub 回的是 404,不是 403 —— 它故意不说资源到底存不存在。
    # 但它在响应头里写明这个接口需要什么 scope,用这个把两种情况分开。
    # (实测过:我们的只读 token 会拿到 404 + x-accepted-oauth-scopes: 'public_repo, repo')
    accepted = r.headers.get("x-accepted-oauth-scopes", "")
    if r.status_code == 404 and accepted:
        raise HTTPException(
            status_code=403,
            detail=f"token 权限不足。GitHub 这个接口要求 {accepted} 权限,当前 token 没有。"
                   "去 github.com/settings/tokens 加上 public_repo —— "
                   "star 属于写操作,只读 token 读数据够用,但 star 不行")
    if r.status_code == 403:
        raise HTTPException(
            status_code=403,
            detail="GitHub 拒绝了这个请求(通常是权限不足或触发了限流)")
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail=f"GitHub 上找不到 {full_name}")
    raise HTTPException(status_code=502, detail=f"GitHub 返回 {r.status_code}")




@app.get("/api/me/starred")
def my_starred(request: Request, limit: int = 200):
    """**当前登录的人** star 过的 repo,按 star 时间倒序 —— 推荐系统的口味来源。"""
    user = require_user(request)
    conn = db.get_conn()
    rows = db.starred_list(conn, user["id"], limit=max(1, min(limit, 1000)))
    items = [dict(r) for r in rows]
    attach_extras(conn, items)
    return {"count": len(items), "items": items}


@app.get("/api/recommend")
def api_recommend(request: Request, limit: int = 20, offset: int = 0,
                  sort: str = "similarity"):
    """P6:内容相似推荐。

    offset 用来"换一批":推荐是按分数排好的一个长列表,把 offset 往后移
    就拿到新的一段,每次都是没看过的新 repo。
    (重算一遍是没用的 —— 同样的输入必然得到同样的排序,等于没换。)

    这里用函数内 import(而不是文件顶部):sklearn 加载要好几秒,
    放顶部的话服务一启动就得等它,而 /api/repos 这些接口根本用不着它。
    """
    from recommend import recommend_for

    user = require_user(request)          # 推荐是"给你"的,必须知道你是谁
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    conn = db.get_conn()
    try:
        items = recommend_for(conn, user["id"], limit, offset, sort)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {
        "count": len(items),
        "offset": offset,
        "has_more": len(items) == limit,      # 还有下一批可换
        "items": items,
    }


@app.get("/api/me/following")
def my_following(request: Request, limit: int = 500, sort: str = "name", q: str = None):
    """我关注的开发者,支持排序和搜索。

    数据来自 GitHub 的 following 列表(由 sync_following.py 同步)——
    是**真实数据**,不是从 star 推出来的。

    sort=name    按用户名(默认)
    sort=recent  按关注时间,新的在前
    sort=oldest  按关注时间,旧的在前
    """
    user = require_user(request)
    conn = db.get_conn()
    rows = db.list_following(conn, user["id"], max(1, min(limit, 2000)),
                             sort=sort, q=(q or "").strip() or None)
    return {
        "count": len(rows),
        "sort": sort,
        "q": q or "",
        "items": [{
            "login": r["login"],
            "name": r["name"],
            "html_url": r["html_url"] or f"https://github.com/{r['login']}",
            "avatar_url": r["avatar_url"],
            "first_seen": r["first_seen"],
        } for r in rows],
    }


MYMEMORY = "https://api.mymemory.translated.net/get"
MAX_CHUNK = 450      # MyMemory 匿名单次上限约 500 字节,留点余量
MAX_TOTAL = 3000     # 再长就不翻了(README 我们本来就截到 2600)


def _chunks(text, size=MAX_CHUNK):
    """按句子边界切块。

    别从句子中间硬切 —— 切在半个句子上,翻译出来就是断的,
    拼回去读着很别扭。
    """
    out, buf = [], ""
    for part in re.split(r"(?<=[.!?。!?;])\s*|\n+", text):
        if not part:
            continue
        if len(buf) + len(part) + 1 <= size:
            buf = (buf + " " + part).strip() if buf else part
        else:
            if buf:
                out.append(buf)
            while len(part) > size:      # 单句就超长,只能硬切
                out.append(part[:size])
                part = part[size:]
            buf = part
    if buf:
        out.append(buf)
    return out


def _translate_one(text, src, tgt):
    try:
        r = requests.get(MYMEMORY, params={"q": text, "langpair": f"{src}|{tgt}"},
                         timeout=20)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"连不上翻译服务:{e}")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"翻译服务返回 {r.status_code}")
    try:
        out = (r.json().get("responseData") or {}).get("translatedText") or ""
    except ValueError:
        out = ""
    if not out:
        raise HTTPException(status_code=502, detail="翻译服务没有返回结果")
    return out


@app.get("/api/translate")
def translate(text: str, to: str = "zh"):
    """把一段文字翻成目标语言。

    用的是 MyMemory 的公开接口:免费、不用申请 key(匿名有每日额度)。
    这个功能是偶尔点一下,不值得为它去申请一个密钥。

    长文本(比如整个 README)会**分块翻译再拼回去** ——
    接口单次只收 500 字节左右,不分块就翻不了。
    源语言靠粗略判断(有汉字就当中文),目标语言跟界面语言走。
    """
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="没有要翻译的内容")
    text = text[:MAX_TOTAL]

    src = "zh-CN" if re.search(r"[一-鿿]", text) else "en"
    tgt = "zh-CN" if (to or "zh").startswith("zh") else "en"
    if src == tgt:
        return {"translated": text, "same_language": True}

    parts = _chunks(text)
    out = []
    for i, part in enumerate(parts):
        out.append(_translate_one(part, src, tgt))
        if i < len(parts) - 1:
            time.sleep(0.25)     # 别把免费接口打爆
    return {"translated": " ".join(out), "source": src, "target": tgt,
            "chunks": len(parts)}


@app.post("/api/events", status_code=201)
def post_event(request: Request, ev: EventIn):
    """记一条反馈。前端点心/不感兴趣就调这里。"""
    user = require_user(request)
    if ev.action not in db.EVENT_ACTIONS:
        raise HTTPException(status_code=422,
                            detail=f"action 只能是 {list(db.EVENT_ACTIONS)}")
    conn = db.get_conn()
    repo_id = db.find_repo_id(conn, ev.full_name)
    if repo_id is None:
        raise HTTPException(status_code=404,
                            detail=f"库里没有 {ev.full_name}")
    db.add_event(conn, user["id"], repo_id, ev.action)
    return {"ok": True, "full_name": ev.full_name, "action": ev.action}


@app.get("/api/events")
def list_events(request: Request, limit: int = 20):
    """**当前登录的人**的反馈流水,最近的在前。

    前端目前不调这个接口(它只 POST 提交反馈),留着是为了排查
    "我当时到底点了什么"。

    ⚠️ 必须 require_user + 按人过滤。原来是全表返回、还不校验登录 ——
    多用户上线后,任何人不登录就能读到所有人的点赞记录。
    """
    user = require_user(request)
    limit = max(1, min(limit, 200))      # 别让 ?limit=999999 拉出整张表
    conn = db.get_conn()
    return {"items": [dict(r) for r in db.recent_events(conn, user["id"], limit)]}


@app.get("/api/opinions")
def my_opinions(request: Request):
    """{full_name: action} —— **当前登录的人**对每个 repo 的最终态度。

    前端拿它给按钮标选中状态:这样改过答案之后,刷新页面还能看出自己选的是哪个。
    """
    user = require_user(request)
    conn = db.get_conn()
    return {"opinions": db.opinion_map(conn, user["id"])}


# ---------------- 前端静态文件 ----------------
# **必须放在文件最末尾。** "/" 会兜住所有路径,只要它在任何一个 API 路由之前注册,
# 后面的接口就永远匹配不到(第一次就踩了这个坑:插在文件中间,导致它之后注册的
# /api/me/starred、/api/recommend 等全部 404)。
# 好处是前后端**同一个端口、同源** —— 不用配 CORS,session cookie 也能正常带。
class NoCacheStatic(StaticFiles):
    """给静态文件加上 no-cache 头。

    为什么需要:默认情况下浏览器会对静态文件做**启发式缓存**,手机浏览器尤其顽固 ——
    改完代码刷新半天看不到新版本,很容易误判成"代码没生效"(我们已经为此浪费过好几轮时间)。

    加上 no-cache 之后,浏览器每次都会问一句"变了没":
    文件没变就返回 304(只有几十字节),变了几毫秒就拿到新的。**既不会看到旧版本,也不会变慢。**
    """

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


_WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
if os.path.isdir(_WEB_DIR):
    app.mount("/", NoCacheStatic(directory=_WEB_DIR, html=True), name="web")
