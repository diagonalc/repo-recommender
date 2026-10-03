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
import hashlib
import os
import re
import urllib.error
import urllib.parse
import urllib.request

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


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

    print("【健康检查】")
    # 不需要登录 —— 探针拿不到 session cookie。顺带确认它的形状没变:
    # 少一个字段,监控那头就会安静地失效。
    body = call("GET", "/api/health")
    if body:
        try:
            h = json.loads(body)
            for k in ("ok", "repos", "last_snapshot", "stale_days"):
                check_field = k in h
                print(f"  {'✅' if check_field else '❌'} /api/health 带 {k} 字段")
                if not check_field:
                    DEAD.append(f"/api/health 缺字段 {k}")
        except Exception as e:
            print(f"  ❌ /api/health 不是 JSON:{e}")
            DEAD.append("/api/health 不是 JSON")

    print("\n【静态托管】")
    call("GET", "/")
    call("GET", "/index.html")
    call("GET", "/app.js")      # CSS 是内联在 index.html 里的,没有单独的样式文件

    # ★ app.js 的版本号必须是**内容哈希**(见 api.py 的 index_page)。
    #
    # 这条值得钉死,因为出问题时的症状极具误导性:写死版本号的话,
    # Cloudflare 会把 app.js 缓存 4 小时(它强制改写静态文件的缓存头,
    # 源站说什么都没用)—— 于是"接口明明更新了,页面纹丝不动",
    # 而服务端这边怎么看都是对的。已经为此白查过一次。
    body = call("GET", "/")
    if body:
        m = re.search(rb"app\.js\?v=([A-Za-z0-9_]+)", body)
        if not m:
            print("  ❌ 首页里的 app.js 没带版本号")
            DEAD.append("首页 app.js 没带版本号")
        elif m.group(1) == b"__ASSET_V__":
            print("  ❌ 版本号占位符没被替换")
            DEAD.append("app.js 版本号占位符未被替换")
        else:
            try:
                with open(os.path.join(WEB_DIR, "app.js"), "rb") as f:
                    want = hashlib.sha256(f.read()).hexdigest()[:10].encode()
            except OSError:
                want = None
            ok = want is not None and m.group(1) == want
            print(f"  {'✅' if ok else '❌'} 版本号是 app.js 的内容哈希  "
                  f"{m.group(1).decode()}")
            if not ok:
                DEAD.append(f"app.js 版本号不是内容哈希(拿到 {m.group(1).decode()})")

    print("\n【榜单 / 筛选】")
    for sort in ["stars", "trending", "pushed", "name"]:
        call("GET", f"/api/repos?sort={sort}&limit=3")
    call("GET", "/api/repos?lang=python&limit=3")
    call("GET", "/api/repos?sort=bogus")
    call("GET", "/api/repos?limit=0")
    call("GET", "/api/repos?limit=99999")

    print("\n【标签】")
    call("GET", "/api/tags")
    # 标签页的搜索:按标签名过滤。
    # 这里不只看它 200,还要验**筛出来的确实都含关键词** ——
    # 过滤条件写错(比如漏了 WHERE)时接口照样返回 200,只是结果是全量。
    for probe in ("rust", "zzzznope"):
        call("GET", f"/api/tags?q={probe}&limit=20")
    body = call("GET", "/api/tags?q=rust&limit=20")
    if body:
        try:
            tags = [x["tag"] for x in json.loads(body)["items"]]
            ok = bool(tags) and all("rust" in x.lower() for x in tags)
            print(f"  {'✅' if ok else '❌'} 筛出来的标签都含 'rust'  {tags[:4]}")
            if not ok:
                DEAD.append("标签搜索结果里混进了不含关键词的")
        except Exception as e:
            DEAD.append(f"标签搜索解析失败:{e}")

    print("\n【搜索】")
    call("GET", "/api/search?q=react")
    call("GET", "/api/search?q=")
    call("GET", "/api/search")                       # 缺参数

    print("\n【搜索排序】")
    for s in ("relevance", "stars", "name", "pushed"):
        call("GET", f"/api/search?q=python&sort={s}&limit=5")
    call("GET", "/api/search?q=python&sort=bogus")   # 非法排序应被拒
    # 光看 200 不够:排序参数被忽略了也会返回 200,只是顺序没变
    body = call("GET", "/api/search?q=python&sort=stars&limit=10")
    if body:
        try:
            vals = [x["stargazers_count"] for x in json.loads(body)["items"]]
            ok = vals == sorted(vals, reverse=True)
            print(f"  {'✅' if ok else '❌'} sort=stars 真的是降序  {vals[:5]}")
            if not ok:
                DEAD.append("搜索 sort=stars 没按降序排")
        except Exception as e:
            DEAD.append(f"搜索排序解析失败:{e}")

    print("\n【头像代理】")
    # 头像现在由服务端转发 + 落盘缓存,不再让浏览器直连 github.com。
    # 直连那会儿每个头像要重新 DNS/TCP/TLS + 一次 302 跳,一页 30 张卡
    # 就是 60 次跨域往返 —— 这是查性能时找出来的最大瓶颈。
    call("GET", "/api/avatar/torvalds")
    # 路径穿越:这个参数直接参与拼路径,必须滤干净
    call("GET", "/api/avatar/..%2F..%2Fetc%2Fpasswd")
    call("GET", "/api/avatar/")

    print("\n【二次元分站】")
    call("GET", "/api/acg?limit=5")                      # 不用登录,应该 200
    for s in ("stars", "pushed", "name", "added"):
        call("GET", f"/api/acg?sort={s}&limit=3")
    call("GET", "/api/acg?sort=bogus")                   # 非法排序应被拒
    call("GET", "/api/acg?q=airi&limit=3")               # 洞里搜索
    call("GET", "/api/acg?tag=voicevox&limit=3")         # 洞里按标签筛
    call("GET", "/api/acg?q=airi&tag=voicevox&limit=3")  # 两个条件叠加
    call("GET", "/api/acg/tags?limit=8")                 # 洞里的标签云
    call("GET", "/api/acg/tags?q=anime&limit=8")
    # 搜到的东西必须**真的都在名单里** —— 漏写 JOIN 的话会捞到主站的仓库,
    # 接口照样返回 200,只是结果多了一堆不相干的
    body = call("GET", "/api/acg?q=airi&limit=20")
    if body:
        try:
            d0 = json.loads(body)
            ok = d0["matched"] <= d0["total"] and d0["count"] <= d0["matched"]
            print(f"  {'✅' if ok else '❌'} 筛选计数自洽  "
                  f"count={d0['count']} matched={d0['matched']} total={d0['total']}")
            if not ok:
                DEAD.append("acg 筛选计数不自洽(可能漏了 JOIN)")
        except Exception as e:
            DEAD.append(f"acg 搜索解析失败:{e}")
    body = call("GET", "/api/acg?sort=stars&limit=8")
    if body:
        try:
            vals = [x["stargazers_count"] for x in json.loads(body)["items"]]
            ok = bool(vals) and vals == sorted(vals, reverse=True)
            print(f"  {'✅' if ok else '❌'} sort=stars 真的是降序  {vals[:5]}")
            if not ok:
                DEAD.append("acg sort=stars 没按降序排")
        except Exception as e:
            DEAD.append(f"acg 解析失败:{e}")

    print("\n【详情】")
    call("GET", "/api/repos/facebook/react")
    call("GET", "/api/repos/这个不存在/xyz")

    print("\n【登录态(未登录应 401,不该 500)】")
    call("GET", "/api/me")
    call("GET", "/api/me/starred")
    call("GET", "/api/me/starred/status")
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
