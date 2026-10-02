#!/usr/bin/env python3
"""全 GitHub 搜索:用户想找什么就现查什么。

和 fetch_repos.py 的区别:
    fetch_repos 是每天按语言拉榜单的**日常采集**,数据长期积累;
    这里是**即时查询** —— 你搜什么就查什么,结果当场用。

为什么查到的结果要 upsert 进本地 repos 表:
    不写进去的话,搜索结果只能看不能用 —— 点名字进不了详情页(本地库里没有),
    点"感兴趣"也会 404。写进去之后它们和库里的 repo 完全一样:
    能看详情、能打标签、能反馈、也能参与后面的相似推荐。

代价:本地候选池会随你搜索而变大。这是有意的 —— 池子本来就该跟着你的兴趣长。
"""
import requests

from fetch_repos import TOKEN

API = "https://api.github.com/search/repositories"


def search_github(q, limit=30):
    """查 GitHub 全站。返回原始 item 列表(和 fetch_repos 拉到的结构一致)。

    GitHub 搜索接口认证后 30 次/分钟 —— 手动搜索完全够用,
    但这不是给批量采集用的。
    """
    headers = {"Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"token {TOKEN}"

    # in:name = 只匹配仓库名字。
    # 不加这个限定的话,GitHub 连描述和 README 一起搜 —— 搜 "terminal file manager"
    # 会返回一堆"描述里提过这几个词"的仓库,而不是名字里真有这些词的。
    # 要找的是"名字含这个字符串的 repo",那就把范围明确收在名字上。
    query = q if "in:" in q.lower() else f"{q} in:name"

    try:
        r = requests.get(API, headers=headers,
                         params={"q": query, "sort": "stars", "order": "desc",
                                 "per_page": max(1, min(limit, 100))},
                         timeout=30)
    except requests.RequestException as e:
        # 网络层错误(代理抖动 / TLS 中断)必须转成 RuntimeError。
        #
        # 调用方 api.py 写的是 `except RuntimeError` → 转 502"连不上 GitHub"。
        # requests 的异常**不是** RuntimeError,不转的话它会直接冒出去
        # 变成 500 Internal Server Error —— 用户以为是我们崩了,
        # 其实是外面连不上,两边都查错方向。
        raise RuntimeError(f"连不上 GitHub:{type(e).__name__}")

    if r.status_code in (403, 429):
        try:
            msg = r.json().get("message", "")
        except ValueError:
            msg = ""
        raise RuntimeError(f"GitHub 限流或拒绝:{msg or r.status_code}")
    if r.status_code != 200:
        raise RuntimeError(f"GitHub 返回 HTTP {r.status_code}")

    return r.json().get("items", [])
