#!/usr/bin/env python3
"""GitHub OAuth 登录。

流程就是标准的授权码模式:
    1. 用户点"登录" → /auth/login → 302 跳到 github.com/login/oauth/authorize
    2. 用户在 GitHub 上确认授权 → 带着 ?code=... 回到 /auth/callback
    3. 我们拿 code 去换 access_token(**这一步要用 client secret,只能服务端做**)
    4. 用 token 拉用户资料 → 建/找用户 → 发会话 cookie

凭据从哪来:`~/.config/repo-recommender/oauth.env`
    REPOS_GH_CLIENT_ID=...
    REPOS_GH_CLIENT_SECRET=...

为什么不放代码里、不进仓库:和 GITHUB_TOKEN 一个道理 ——
client secret 泄露,别人就能冒充你的应用去骗用户的授权。
"""
import os
import secrets
from urllib.parse import urlencode

import requests

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_API = "https://api.github.com/user"

ENV_PATH = os.path.expanduser("~/.config/repo-recommender/oauth.env")
CALLBACK_PATH = "/auth/callback"

# 公开访问地址(线上必设)。
#
# 为什么不能从请求里推:放在反向代理/隧道后面时,请求到达 uvicorn 的样子
# 和用户看到的不一样 —— Cloudflare 在边缘终止了 HTTPS,转发给本地的是**明文 http**,
# 于是 request.base_url 算出来是 http://... 而用户看到的是 https://...
# 两者对不上,GitHub 会以 redirect_uri mismatch 拒绝。
#
# 所以线上直接把"用户实际打开的地址"配在这儿:
#   REPOS_PUBLIC_BASE=https://diagonalc.dpdns.org
PUBLIC_BASE = os.environ.get("REPOS_PUBLIC_BASE", "").rstrip("/")


def redirect_uri(request_base_url):
    """算 OAuth 回调地址:配了 PUBLIC_BASE 就用它,没配才从请求里推(本地开发用)。"""
    base = PUBLIC_BASE or (request_base_url or "").rstrip("/")
    return base + CALLBACK_PATH

# 要哪些权限:
#   read:user   读用户资料(昵称、头像)
#   public_repo 给公开仓库点 star —— 这是**写操作**,read:user 不够。
#               没有它的话,点星会被 GitHub 拒(而且它回的是 404,不是 403)
SCOPES = "read:user public_repo"


def load_env():
    """读 oauth.env。每次都重新读 —— 改完凭据不用重启服务。"""
    conf = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                conf[key.strip()] = value.strip()
    return conf


def credentials():
    """返回 (client_id, client_secret)。环境变量优先,文件兜底。"""
    conf = load_env()
    return (os.environ.get("REPOS_GH_CLIENT_ID") or conf.get("REPOS_GH_CLIENT_ID"),
            os.environ.get("REPOS_GH_CLIENT_SECRET") or conf.get("REPOS_GH_CLIENT_SECRET"))


def configured():
    cid, secret = credentials()
    return bool(cid and secret)


def new_state():
    """防 CSRF 的随机串:登录时发一个、存在 cookie 里,回调时比对。"""
    return secrets.token_urlsafe(24)


def authorize_url(client_id, redirect_uri, state):
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": state,
        "allow_signup": "true",
    })


def exchange_code(code, redirect_uri):
    """拿 code 换 access_token。"""
    client_id, client_secret = credentials()
    try:
        r = requests.post(
            TOKEN_URL, timeout=20,
            headers={"Accept": "application/json"},
            data={"client_id": client_id, "client_secret": client_secret,
                  "code": code, "redirect_uri": redirect_uri})
    except requests.RequestException as e:
        # 连不上 GitHub(代理挂了、被墙了)—— 报清楚,别让它变成一句 500
        raise RuntimeError(f"连不上 GitHub 换取 token:{type(e).__name__}。"
                           "检查代理是否正常")
    if r.status_code != 200:
        raise RuntimeError(f"换 token 失败:HTTP {r.status_code} {r.text[:200]}")
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"换 token 失败:{data.get('error_description') or data['error']}")
    token = data.get("access_token")
    if not token:
        raise RuntimeError("GitHub 没返回 access_token")
    return token


def fetch_user(token):
    """用 token 拉这个人的资料。返回统一成我们要的字段。"""
    try:
        r = requests.get(USER_API, timeout=20, headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"})
    except requests.RequestException as e:
        # 和 exchange_code 同一个道理:网络层的异常不是 RuntimeError,
        # 不接住就会穿过 /auth/callback 的 `except RuntimeError` 变成 500。
        # 这一步失败意味着"code 换到了 token,但拿不到用户资料" ——
        # 报清楚,别让用户以为是自己操作错了。
        raise RuntimeError(f"连不上 GitHub 拉取用户资料:{type(e).__name__}。"
                           "检查代理是否正常")
    if r.status_code != 200:
        raise RuntimeError(f"拉用户资料失败:HTTP {r.status_code}")
    d = r.json()
    return {
        "id": d.get("id"),            # gh_id —— GitHub 的用户 id,身份用它,不用 login(能改)
        "login": d.get("login"),
        "name": d.get("name"),
        "avatar_url": d.get("avatar_url"),
        "token": token,               # 存起来:同步他的 star/关注、替他 star 都要用
    }
