#!/usr/bin/env python3
"""两个同步脚本共用的东西:分页取数 + 错误类型。

为什么单独开一个文件:
    sync_stars.py 和 sync_following.py 的取数逻辑几乎一样
    (翻页、鉴权头、错误处理),各写一份迟早会写歪。
    而把共用的放进其中任意一个、让另一个去 import,读起来像
    "关注依赖 star" —— 其实它们没有依赖关系,只是刚好长得像。
"""
import requests


class SyncAuthError(RuntimeError):
    """token 失效 —— **重试没有意义**,要人去重新登录。

    单独一个类型,是为了让定时任务区分两种失败:
      · 网络抖了      → 值得重试
      · token 过期了  → 重试一百次结果一样,纯粹浪费

    它继承 RuntimeError,所以"只接 RuntimeError"的调用点照常能接住。
    """


def fetch_page(url, token, page, per_page=100,
               accept="application/vnd.github+json"):
    """拉一页。失败时抛 SyncAuthError(要人处理)或 RuntimeError(可以重试)。"""
    headers = {"Accept": accept}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        r = requests.get(url, headers=headers,
                         params={"per_page": per_page, "page": page}, timeout=30)
    except requests.RequestException as e:
        # 网络层错误必须转成 RuntimeError。
        # requests 的异常**不是** RuntimeError —— 不转的话它会穿过调用方的
        # `except RuntimeError`,把一个人的网络抖动放大成整个定时任务失败。
        # 这个坑在 fetch_repos.py 上真实发生过一次(丢了整整一天的快照)。
        raise RuntimeError(f"连不上 GitHub:{type(e).__name__}")
    if r.status_code == 401:
        raise SyncAuthError("token 无效或已过期,重新登录一次")
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()
