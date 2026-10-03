#!/usr/bin/env python3
"""P5:FastAPI 后端 —— 把库里的数据通过 HTTP 接口暴露出去。

启动:
    .venv/bin/uvicorn api:app --reload --port 8000

然后浏览器打开 http://127.0.0.1:8000/docs
—— 这是 FastAPI 白送的交互式文档,每个接口都能当场点着试,不用写 curl。
"""
import hashlib
import heapq
import json
import os
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import requests

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (HTMLResponse, JSONResponse, RedirectResponse,
                               Response)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import auth
import db
import ratelimit

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


def limited(name, limit, window=60):
    """做一个"限流依赖"。

    用法:
        @app.post("/api/events")
        def post_event(request: Request, ev: EventIn,
                       _: None = Depends(limited("events", 60))):
            ...

    阈值定得都**很宽** —— 正常人手动点根本碰不到。它拦的不是攻击者
    (那要靠 Cloudflare),而是"一个人手滑或脚本把公共额度用光":
    全站搜索和抓 README 走的是共享的 GitHub token,30 次/分钟;
    翻译走的是 MyMemory 的匿名额度。这些被别人打光之后,
    受害者是**其他用户**,而且他们完全不知道发生了什么。
    """
    def dep(request: Request):
        key = f"{name}:{ratelimit.client_ip(request)}"
        if not ratelimit.allow(key, limit, window):
            raise HTTPException(
                status_code=429,
                detail=f"操作太频繁了(每 {window} 秒最多 {limit} 次),歇一会儿再试")
    return dep


def github_search_limit(request: Request):
    """只对**全站搜索**限流(scope=github)。

    本地库搜索是纯 SQLite 查询,再频繁也伤不到谁,没必要管;
    全站搜索会去打 GitHub,用的是**共享的**认证额度(30 次/分钟)。
    一个人连点几下,其他人就都搜不了 —— 而他们不会知道是被谁连累的。

    所以这里按 query 参数**有条件地**限:同一个接口,贵的那个分支才限。
    """
    if request.query_params.get("scope") != "github":
        return
    key = f"ghsearch:{ratelimit.client_ip(request)}"
    if not ratelimit.allow(key, 20, 60):
        raise HTTPException(
            status_code=429,
            detail="全站搜索太频繁了(每分钟最多 20 次)。它用的是共享的 GitHub "
                   "额度,慢一点让其他人也能用。")


def cookie_secure(request: Request):
    """这个响应该不该给会话 cookie 加 Secure 标志?

    Secure 的含义是"浏览器只通过 https 发送它" —— 该加。
    但它会让**本机 http 访问**彻底拿不到 cookie(127.0.0.1:18080 是 http),
    也就是"本地登不上",所以不能无脑加。

    判断依据**不能**是 request.url.scheme:cloudflared 是直连 localhost 的,
    本地这一跳永远是 http,从请求本身看不出用户实际走的是 https。
    (这正是当初 redirect_uri 踩过的坑 —— 那次也是被"本地这一跳是明文"骗了。)

    所以:配了 https 的公开地址 + 这个请求不是从本机来的 → 加。
    本机调试照旧能登录。
    """
    if not auth.PUBLIC_BASE.startswith("https://"):
        return False
    host = (request.url.hostname or "").lower()
    return host not in ("127.0.0.1", "localhost", "::1")


@app.get("/api/health")
def health():
    """健康检查 —— 服务活着吗、数据库通不通、**数据新不新鲜**。

    故意**不要求登录**:外部监控探针没有你的 session cookie。
    所以这里只回答"服务本身的状态",不碰任何用户数据。

    为什么还要报"数据新不新鲜":
        这个项目已经栽过一次 —— 每日任务连着两天没跑(09-29、10-01),
        而**页面完全看不出来**:老数据照样渲染,trending 照样出榜,
        只是数字不再变。没有这个字段的话,只能靠人去翻日志才会发现。
        (同样的思路在做 token 失效提示时也用了一次。)

    字段:
        ok            false = 服务或数据库有问题(同时返回 503)
        stale_days    最新快照距今天数。正常 ≤1;连着变大就是每日任务挂了
        warn          超过 2 天才会出现的一行提醒
    """
    out = {"ok": True}
    try:
        conn = db.get_conn()
        snap = conn.execute(
            "SELECT MAX(snapshot_date) FROM repo_snapshots").fetchone()[0]
        out["repos"] = conn.execute("SELECT COUNT(*) FROM repos").fetchone()[0]
        out["snapshots"] = db.count_snapshots(conn)
        out["last_snapshot"] = snap
        if snap:
            from datetime import date
            days = (date.today() - date.fromisoformat(snap)).days
            out["stale_days"] = days
            # 快照存的是 UTC 日期,和本地日期最多差一天 —— 所以 2 天以内都算正常
            if days > 2:
                out["warn"] = f"最新快照是 {days} 天前的 —— 每日任务可能挂了"
    except Exception as e:                  # noqa: BLE001
        # 健康检查本身**绝不能抛 500** —— 它的职责就是"报告坏了没",
        # 自己崩掉等于什么都没说。所有异常都收成 ok=false + 503。
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {e}"
        return JSONResponse(out, status_code=503)
    return out


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
                    secure=cookie_secure(request),
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
            # 上一次拿他的 token 请求 GitHub 成功了没有(每日同步时更新)。
            # 前端据此决定要不要挂一条"授权失效,去重新登录"的提示。
            # token 失效本身是**完全静默**的:页面照开、推荐照出(用的旧数据),
            # 只有新 star 不再进来 —— 不主动说,用户不会知道。
            "token_ok": bool(user["token_ok"]),
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


def _sort_search_items(items, sort):
    """给**全站搜索**的结果排在本地(就地排)。

    本地搜索的排序在 SQL 里做(db.search_repos),因为要靠 LIMIT 截断 ——
    先全查出来再在 Python 里排,等于把整库拉进内存。
    全站搜索没有这个问题:结果本来就只有几十条,而且已经在内存里了。

    每种排序都以 full_name 兜底,理由同 db.SEARCH_SORTS:
    **ORDER BY 得落到唯一值上**,否则并列的那些顺序不定,刷新一下位置就跳。
    """
    if sort == "stars":
        items.sort(key=lambda x: (-(x.get("stargazers_count") or 0),
                                  (x.get("full_name") or "").lower()))
    elif sort == "name":
        items.sort(key=lambda x: (x.get("full_name") or "").lower())
    elif sort == "pushed":
        # pushed_at 可能为 NULL —— 用空串兜底,让它排到最后
        items.sort(key=lambda x: (x.get("pushed_at") or "",
                                  x.get("full_name") or ""),
                   reverse=True)
    return items


@app.get("/api/search")
def search(request: Request, q: str, scope: str = "local", limit: int = 60,
           sort: str = "relevance",
           _: None = Depends(github_search_limit)):
    """搜索 repo。

    scope=local   只搜本地库(名字 / 描述 / 标签 / README)
    scope=github  搜整个 GitHub,现查现用

    sort=relevance(默认) 相关度:本地是"命中位置分级"(名字 > 描述 > 标签 > README),
                        全站是 GitHub 自己给的顺序
    sort=stars / name / pushed   另外三种

    全站搜索的结果会并入本地 repos 表 —— 不写进去的话,结果只能看不能用:
    点名字进不了详情页(本地库没有)、点"感兴趣"会 404。
    写进去之后它们和库里的 repo 完全一样,代价是候选池会随搜索变大(这是好事)。
    """
    q = (q or "").strip()
    if not q:
        raise HTTPException(status_code=422, detail="搜索关键词不能为空")
    if sort not in db.SEARCH_SORTS:
        raise HTTPException(
            status_code=422, detail=f"sort 只能是 {sorted(db.SEARCH_SORTS)}")

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

        # 先按 GitHub 返回的顺序排(它已按 star 排好),别被数据库的返回顺序打乱
        order = {r.get("full_name"): i for i, r in enumerate(raw)}
        items.sort(key=lambda it: order.get(it["full_name"], 9999))
        # "相关度"就用 GitHub 给的顺序;选了别的再在本地重排
        if sort != "relevance":
            _sort_search_items(items, sort)

        attach_extras(conn, items)
        return {"q": q, "scope": "github", "sort": sort,
                "count": len(items), "items": items}

    rows = db.search_repos(conn, q, limit, sort)
    items = [row_to_repo(r) for r in rows]
    for it in items:
        it.pop("rank", None)          # 排序用的内部字段,不用给前端
    attach_extras(conn, items)
    return {"q": q, "scope": "local", "sort": sort,
            "count": len(items), "items": items}


AVATAR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "avatars")


@app.get("/api/avatar/{login}")
def avatar(login: str):
    """头像代理:由我们转发 GitHub 的头像,并落盘缓存。

    **为什么不能让浏览器直接去 github.com 取**(原来就是这么做的,是性能瓶颈):

      1. 那是**另一个域名** —— 浏览器得重新 DNS、TCP、TLS,而且这些都要走代理;
      2. `github.com/<用户>.png` 是 **302 跳**到 avatars.githubusercontent.com,
         等于每次要**两轮往返**;
      3. 一页 30 张卡就是 60 次跨域往返。实测**单个头像要 20 秒以上**(直接超时),
         而服务端处理一个列表接口只要 0.01 秒 —— 也就是说页面几乎所有时间
         都花在等头像上。

    改成本机转发之后:
      · **同一个域名** —— 复用页面已经建好的那条连接,不重新握手;
      · 没有跳转链;
      · 服务器抓过一次就存盘,之后是本地读文件(微秒级);
      · 顺带绕开了"github.com 在墙内不稳定"这件事。

    找不到头像时也缓存一个空标记 —— 不然每次翻到同一个用户都要再问一次 GitHub。
    """
    # GitHub 用户名只含字母数字和连字符。过滤一遍是**防路径穿越**:
    # 这个参数直接参与拼路径,不滤的话 ../../ 就能读到仓库外的东西。
    login = re.sub(r"[^A-Za-z0-9-]", "", login or "")
    if not login:
        raise HTTPException(status_code=404, detail="没有这个头像")

    path = os.path.join(AVATAR_DIR, login.lower() + ".png")
    if not os.path.exists(path):
        os.makedirs(AVATAR_DIR, exist_ok=True)
        try:
            r = requests.get(f"https://github.com/{login}.png?size=80",
                             timeout=20)
        except requests.RequestException:
            # 抓不到就回一个透明像素,别让页面为了一个头像卡住 ——
            # 前端的 onerror 也会把破图换成一个灰圆
            return _transparent_png()
        if r.status_code != 200 or not r.content:
            with open(path, "wb") as f:      # 空文件 = "问过了,没有"
                pass
        else:
            with open(path, "wb") as f:
                f.write(r.content)

    if os.path.getsize(path) == 0:
        return _transparent_png()
    return Response(content=open(path, "rb").read(), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=604800"})


# 1×1 透明 PNG。写死在代码里,免得为了一个占位图再去读文件。
_TRANSPARENT_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6300010000050001" "0d0a2db40000000049454e44ae426082")


def _transparent_png():
    return Response(content=_TRANSPARENT_PNG, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/acg")
def acg_list(sort: str = "stars", limit: int = 60, offset: int = 0,
             tag: list[str] = Query(default=None), q: str = None):
    """兔子洞的列表。

    **不需要登录** —— 它是个公开的浏览页,和 /api/repos 一样。
    也正因为如此,这里**不碰任何用户数据**(没有 user、没有 starred):
    想往这个接口加用户相关的东西之前先想清楚,它是给所有人看的。

    数据来自 acg_repos 表,由 fetch_acg.py 按关键词搜出来 ——
    和候选池(每天采集的那批)是两回事,理由见 schema.sql 里的说明。

    q / tag **都只在这份名单里筛**,不会把主站那几万个仓库捞进来。
    这是分站和主站接口最本质的区别。
    """
    if sort not in db.ACG_SORTS:
        raise HTTPException(
            status_code=422, detail=f"sort 只能是 {sorted(db.ACG_SORTS)}")
    limit = max(1, min(limit, 200))
    tags = [x for x in (tag or []) if x]
    q = (q or "").strip() or None

    conn = db.get_conn()
    rows = db.list_acg(conn, sort=sort, limit=limit, offset=max(0, offset),
                       tags=tags, q=q)
    items = [row_to_repo(r) for r in rows]
    for it in items:
        it.pop("rank", None)          # 排序用的内部字段,不用给前端
    attach_extras(conn, items)
    return {"sort": sort, "q": q, "tags": tags, "count": len(items),
            # matched = 筛完之后有多少条。前端要拿它显示"共 N 个,这里 M 个"——
            # 只给 total 的话,筛完还显示名单总数,看着像坏了
            "matched": db.count_acg_filtered(conn, tags=tags, q=q),
            "total": db.count_acg(conn), "items": items}


@app.get("/api/acg/tags")
def acg_tag_cloud(q: str = None, limit: int = 200):
    """兔子洞的标签云 —— 只统计**名单里**的仓库。

    不能直接用主站的 /api/tags:那是全库的标签云,
    点进去会跳到"全站带这个标签的仓库",而分站里应该只看到名单里的。
    """
    conn = db.get_conn()
    q = (q or "").strip() or None
    rows = db.acg_tags(conn, limit=max(1, min(limit, 500)), q=q)
    return {"count": len(rows), "q": q, "items": [dict(r) for r in rows]}


@app.get("/api/tags")
def list_tags(q: str = None, limit: int = 200):
    """所有标签 + 各自带多少个 repo。

    标签就是 GitHub 的 topics —— 它们是仓库作者自己选的,
    质量比我们瞎猜的关键词高得多,拿来当分类最省事。

    q 按**标签名**过滤(标签页上的搜索框)。过滤在 SQL 里做,
    这样冷门标签也搜得到 —— 详见 db.list_tags 的注释。
    """
    conn = db.get_conn()
    q = (q or "").strip() or None
    rows = db.list_tags(conn, limit=max(1, min(limit, 500)), q=q)
    return {
        "count": len(rows),
        "q": q,
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
def post_comment(request: Request, full_name: str, c: CommentIn,
                 _: None = Depends(limited("comment", 20))):
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
def star_repo(request: Request, full_name: str,
              _: None = Depends(limited("star", 30))):
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
    if r.status_code == 401:
        # 这个人的 GitHub 授权失效了。
        #
        # 注意**不能回 401**:前端的 needLogin() 把 401 理解成"你的登录会话没了",
        # 会直接把页面切成登录页。但这里的情况是**会话好着呢,只是 GitHub 那边的
        # 授权旧了** —— 两件不同的事,不能共用一个状态码。
        #
        # 顺便把状态记进库:这样页面顶部那条"去重新登录"的提示立刻就能出现,
        # 不用等明天的定时同步才发现。
        db.set_token_status(conn, user["id"], False)
        raise HTTPException(
            status_code=403,
            detail="你的 GitHub 授权已失效(Bad credentials)。重新登录一次就能恢复,"
                   "已有的数据都还在")
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


# "还活着吗"的分档。阈值是**口径**,不是事实 —— 放这儿方便调。
# 30 天 / 一年是常见直觉:一个月内有提交算活着,一年没动基本就是弃了。
HEALTH_ACTIVE_DAYS = 30
HEALTH_SLOW_DAYS = 365

STARRED_STATUS_SORTS = ["growth", "stale", "recent", "stars"]


@app.get("/api/me/starred/status")
def starred_status(request: Request, sort: str = "growth"):
    """你 star 过的仓库**现在怎么样了**。

    两个维度:
      · **还活着吗** —— 按最后一次 push 距今多久分档(活跃 / 放缓 / 停更)
      · **在涨吗**   —— 最近两个快照之间的 star 增量

    ⚠️ 一个必须说清的限制:**我们并不知道"你 star 它的时候它多少星"。**
       快照是 2026-09 才开始攒的,在那之前 star 的历史没有留档。
       所以这里只能比"最近这几天涨了多少",**算不出**"从你 star 到现在涨了多少"。
       前端也别写那种话 —— 数据支持不了,写了就是编。

    排序:
        growth  最近涨得最快(没增量数据的排最后)
        stale   最久没更新的排前面 —— 想看"我 star 的东西都死没死"就用它
        recent  最近 star 的排前面
        stars   星数最多的排前面
    """
    user = require_user(request)
    if sort not in STARRED_STATUS_SORTS:
        raise HTTPException(
            status_code=422, detail=f"sort 只能是 {STARRED_STATUS_SORTS}")

    conn = db.get_conn()
    rows = db.starred_list(conn, user["id"], limit=1000)

    # 最近两个快照之间的增量。只有进了快照的仓库才有(候选池约 1200 个),
    # 落在池子外的 star 仓库 delta 就是 None —— 前端显示成"—",不是 0。
    dates = db.snapshot_dates(conn)
    growth = {}
    if len(dates) >= 2:
        growth = {r["id"]: r["delta"] for r in db.growth_rows(conn, dates[0], dates[1])}

    now = datetime.now(timezone.utc)
    items = []
    for r in rows:
        days = None
        if r["pushed_at"]:
            try:
                t = datetime.strptime(r["pushed_at"], "%Y-%m-%dT%H:%M:%SZ")
                days = (now - t.replace(tzinfo=timezone.utc)).days
            except ValueError:
                days = None       # 时间格式不对就当不知道,别让整个接口挂掉

        if days is None:
            health = "unknown"
        elif days <= HEALTH_ACTIVE_DAYS:
            health = "active"
        elif days <= HEALTH_SLOW_DAYS:
            health = "slowing"
        else:
            health = "stale"

        items.append({
            "full_name": r["full_name"],
            "language": r["language"],
            "html_url": r["html_url"],
            "stargazers_count": r["stargazers_count"],
            "starred_at": r["starred_at"],
            "pushed_at": r["pushed_at"],
            "days_since_push": days,
            "health": health,
            "delta": growth.get(r["id"]),      # None = 不在快照池子里 / 库还太新
        })

    if sort == "growth":
        items.sort(key=lambda x: (x["delta"] is None, -(x["delta"] or 0)))
    elif sort == "stale":
        items.sort(key=lambda x: -(x["days_since_push"] or -1))
    elif sort == "recent":
        items.sort(key=lambda x: x["starred_at"] or "", reverse=True)
    else:                                      # stars
        items.sort(key=lambda x: -(x["stargazers_count"] or 0))

    counts = {}
    for it in items:
        counts[it["health"]] = counts.get(it["health"], 0) + 1

    return {"count": len(items), "sort": sort, "health_counts": counts,
            "since": dates[1] if len(dates) >= 2 else None,
            "as_of": dates[0] if len(dates) >= 2 else None,
            "items": items}


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
def translate(request: Request, text: str, to: str = "zh",
              _: None = Depends(limited("translate", 20))):
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
def post_event(request: Request, ev: EventIn,
               _: None = Depends(limited("events", 60))):
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
    """给静态文件加上"每次都回来问一句"的缓存头。

    为什么需要:默认情况下浏览器会对静态文件做**启发式缓存**,手机浏览器尤其顽固 ——
    改完代码刷新半天看不到新版本,很容易误判成"代码没生效"。

    ⚠️ 光写 `no-cache` **不够**,而且写 `max-age=0` 也没用 —— 走 Cloudflare 时会被它顶掉。

    实测(试过两种写法,结果一样):
        源站发 `Cache-Control: no-cache`            → CF 回给浏览器 max-age=14400
        源站发 `Cache-Control: no-cache, max-age=0, must-revalidate`
                                                   → CF 回给浏览器 max-age=14400
        (只有 `must-revalidate` 被保留了)

    也就是说:**对 .js / .css 这类静态扩展名,Cloudflare 会强行套上它自己的
    Browser Cache TTL 默认值(4 小时),源站说了不算。**
    症状极具误导性:接口已经更新了、页面却纹丝不动,而服务端这边怎么看都是对的。
    (有一次为此白查了半天,最后发现浏览器里那份 JS 是四个小时前的。)

    真正解决问题的是**把版本号绑到文件内容上**(见下面 index_page 和
    _app_asset_version):URL 变了,浏览器就当它是新文件。
    这个头留着是有用的兜底 —— 直连(127.0.0.1)、或者哪天不走 Cloudflare 了,
    它就能按原意工作。
    """

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
        return resp


_WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def _asset_version(filename):
    """按内容算版本号(取哈希前 10 位)。

    内容没变 → 哈希没变 → URL 没变 → 浏览器直接用缓存(不浪费流量)。
    内容变了 → 哈希变了 → URL 变了 → 浏览器必定重新下载。
    **这才是缓存该有的样子**:该省的一分不省,该新的绝不旧。
    """
    try:
        with open(os.path.join(_WEB_DIR, filename), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:10]
    except OSError:
        return "0"


# 需要往 HTML 里注入版本号的资源:占位符 → 文件名。
# 再加资源就往这儿加一行,**同时**在 index.html 里用对应的占位符。
#
# 为什么连字体也要版本化:它和 app.js 一样会被 Cloudflare 强制缓存 4 小时
# (见 NoCacheStatic 的说明),而没有版本号的 URL 换不了。
# 真踩过:改完字体文件,浏览器里那份坏的还是照用,页面看起来"一点没变"。
ASSET_TOKENS = {
    "__ASSET_V__": "app.js",
    "__FONT_V__": "acg-title.woff2",
}


@app.get("/")
@app.get("/index.html")
def index_page():
    """首页 —— 每次现算 app.js 的版本号填进 HTML。

    ⚠️ 为什么这里要绕开 StaticFiles、自己读文件返回:

        静态文件的缓存头会被 Cloudflare 改写(见 NoCacheStatic 的说明),
        客户端拿到的是"缓存 4 小时"。**如果 HTML 也那样被冻住,
        里面写的版本号就一起冻住了** —— 改了代码也传不下去,
        整个缓存失效机制等于白做。

        而 **HTML 恰好不会被 Cloudflare 缓存**:它只缓存 .js/.css 这类
        静态扩展名,首页实测是 `cf-cache-status: DYNAMIC`(不缓存边缘副本),
        而且缓存头原样透传。

        所以 HTML 是唯一能"每次都现算"的位置 —— 版本号必须在这里注入。

    注:这两条路由必须注册在末尾那个 mount("/") **之前**。
    路由按注册顺序匹配,mount 放最后才轮得到它兜底。
    """
    try:
        with open(os.path.join(_WEB_DIR, "index.html"), encoding="utf-8") as f:
            html = f.read()
    except OSError:
        raise HTTPException(status_code=500, detail="web/index.html 不见了")
    for token, filename in ASSET_TOKENS.items():
        html = html.replace(token, _asset_version(filename))
    return HTMLResponse(
        html,
        headers={"Cache-Control": "no-cache, max-age=0, must-revalidate"})


if os.path.isdir(_WEB_DIR):
    app.mount("/", NoCacheStatic(directory=_WEB_DIR, html=True), name="web")
