#!/usr/bin/env python3
"""冒烟测试:把每个 HTTP 端点都打一遍,重点抓 500。

为什么要有这个:项目没有单元测试,改完之后"看起来没坏"全靠手动点网页。
但网页只会暴露你**碰巧点到**的那条路径 —— 一个只在下拉刷新时才走的接口,
可能已经坏了几个月没人发现。

这个脚本不判断业务逻辑对不对(那要靠人看),只判断"这个端点还活着":
    · 2xx / 3xx / 4xx(带正常错误信息)= 活着
    · 5xx 或连接异常                 = 死了,必须修

用法(先确保服务在跑):
    .venv/bin/python tests/smoke_api.py            # 默认打 127.0.0.1:18080
    .venv/bin/python tests/smoke_api.py 8000       # 换端口
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """3xx 也当结果报出来,别跟着跳。

    /auth/login 会 302 到 github.com —— 跟着跳的话这个"本地冒烟测试"
    就变成在测 GitHub 通不通了(而且会超时),完全跑偏。
    我们要验的是"它到底有没有乖乖 302"。
    """
    def redirect_request(self, *a, **k):
        return None


PORT = sys.argv[1] if len(sys.argv) > 1 else "18080"
BASE = f"http://127.0.0.1:{PORT}"
# 走代理的话本地请求会被 mihomo 拦下来(还回一个假的 502)
opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({}), NoRedirect)

DEAD = []
SLOW = []


def call(method, path, body=None, note=""):
    # 非 ASCII 路径要转义 —— 不然 urllib 在**客户端**就抛 UnicodeEncodeError,
    # 看着像服务端的 bug,其实是测试自己没编码。(
    # 真实的仓库名可能有中文,所以这条路径值得测。)
    url = BASE + urllib.parse.quote(path, safe="/?&=%")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    label = f"{method:6} {path}"
    try:
        with opener.open(req, timeout=25) as r:
            code = r.status
            payload = r.read()
    except urllib.error.HTTPError as e:
        code = e.code
        payload = e.read()
    except Exception as e:
        print(f"  ❌ {label}  连接异常 {type(e).__name__}: {e}")
        DEAD.append(f"{label} ({type(e).__name__})")
        return None

    # 5xx 一定是 bug;4xx 是正常的"你参数不对/没登录"
    icon = "✅" if code < 500 else "❌"
    if code >= 500:
        DEAD.append(label)

    detail = ""
    if code >= 400:
        try:
            detail = json.loads(payload).get("detail", "")[:90]
        except Exception:
            detail = payload[:90].decode("utf-8", "replace")
    print(f"  {icon} {label} → {code}  {detail}")
    return payload


def main():
    print(f"打 {BASE}\n")

    print("【静态托管】")
    call("GET", "/")
    call("GET", "/index.html")
    call("GET", "/app.js")      # CSS 是内联在 index.html 里的,没有单独的样式文件

    print("\n【榜单 / 筛选】")
    for sort in ["stars", "trending", "pushed", "name"]:
        call("GET", f"/api/repos?sort={sort}&limit=3")
    call("GET", "/api/repos?lang=python&limit=3")
    call("GET", "/api/repos?sort=bogus")
    call("GET", "/api/repos?limit=0")
    call("GET", "/api/repos?limit=99999")

    print("\n【标签】")
    call("GET", "/api/tags")

    print("\n【搜索】")
    call("GET", "/api/search?q=react")
    call("GET", "/api/search?q=")
    call("GET", "/api/search")                       # 缺参数

    print("\n【详情】")
    call("GET", "/api/repos/facebook/react")
    call("GET", "/api/repos/这个不存在/xyz")

    print("\n【登录态(未登录应 401,不该 500)】")
    call("GET", "/api/me")
    call("GET", "/api/me/starred")
    call("GET", "/api/me/following")
    call("GET", "/api/recommend")
    call("GET", "/api/events")
    call("GET", "/api/opinions")
    call("POST", "/api/events", {"repo_id": 1, "action": "interested"})
    call("POST", "/api/comments/facebook/react", {"body": "x"})
    call("POST", "/api/star/facebook/react")
    call("POST", "/api/events", {"repo_id": 1, "action": "不存在的动作"})

    print("\n【翻译】")
    call("GET", "/api/translate?text=hello&to=zh")
    call("GET", "/api/translate")

    print("\n【OAuth】")
    call("GET", "/auth/login")

    print()
    if DEAD:
        print(f"❌ {len(DEAD)} 个端点返回 5xx 或连不上:")
        for d in DEAD:
            print(f"     {d}")
        sys.exit(1)
    print("✅ 所有端点都没有 5xx")


if __name__ == "__main__":
    main()
