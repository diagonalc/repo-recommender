#!/usr/bin/env python3
"""回归测试:网络层错误必须变成 RuntimeError,不能炸掉整个 job。

背景 —— 2026-10-02 那次事故:
    GitHub 请求抛了 requests.exceptions.SSLError(代理抖了一下),
    它不是 RuntimeError,于是穿过 collect_repos 的 `except RuntimeError`
    一路冒到 main(),整个 job 崩溃。那天 12 个语言已经成功拿到 8 个,
    结果**一个都没入库**,丢掉一整天快照。

    trending 靠"相邻两天的快照"算增速 —— 丢一天就是丢一天的数据,补不回来。

跑法:
    .venv/bin/python tests/test_fetch_retry.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

import daily_update
import fetch_repos

FAILED = []


def check(name, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def freeze(module):
    """把 sleep 换掉,别让测试真等 5+10+15 秒。"""
    module.time.sleep = lambda s: None
    daily_update.time.sleep = lambda s: None


def main():
    freeze(fetch_repos)

    # ---- 1. SSL 错误(10-02 那次的原型)---------------------------------
    calls = []
    def ssl_boom(*a, **k):
        calls.append(1)
        raise requests.exceptions.SSLError("SSL: UNEXPECTED_EOF_WHILE_READING")
    fetch_repos.requests.get = ssl_boom

    print("1. SSL 错误")
    try:
        fetch_repos.fetch_page("go", 2)
        check("抛异常", False, "居然没抛")
    except RuntimeError:
        check("抛的是 RuntimeError", True, f"(重试 {len(calls)} 次)")
    except BaseException as e:
        check("抛的是 RuntimeError", False,
              f"实际是 {type(e).__name__} —— 它会炸掉整个 job")

    # ---- 2. 连接超时(另一类网络错误)-------------------------------
    calls.clear()
    def timeout_boom(*a, **k):
        calls.append(1)
        raise requests.exceptions.ConnectTimeout("timed out")
    fetch_repos.requests.get = timeout_boom

    print("2. 连接超时")
    try:
        fetch_repos.fetch_page("rust", 1)
        check("抛异常", False, "居然没抛")
    except RuntimeError:
        check("抛的是 RuntimeError", True, f"(重试 {len(calls)} 次)")
    except BaseException as e:
        check("抛的是 RuntimeError", False, f"实际是 {type(e).__name__}")

    # ---- 3. 网络先坏后好:应该重试成功,而不是放弃 --------------------
    print("3. 前两次网络故障、第三次成功(重试真的起作用吗)")
    state = {"n": 0}

    class FakeResp:
        status_code = 200
        headers = {"X-RateLimit-Remaining": "29"}
        def json(self):
            return {"items": [{"id": 1, "full_name": "a/b"}]}

    def flaky(*a, **k):
        state["n"] += 1
        if state["n"] < 3:
            raise requests.exceptions.SSLError("flaky")
        return FakeResp()
    fetch_repos.requests.get = flaky

    try:
        items = fetch_repos.fetch_page("python", 1)
        check("重试后拿到数据", items and items[0]["full_name"] == "a/b",
              f"(第 {state['n']} 次成功)")
    except BaseException as e:
        check("重试后拿到数据", False, f"抛了 {type(e).__name__}")

    # ---- 4. collect_repos 真的只跳过失败语言,不中断整轮 -----------------
    print("4. 全部语言都网络故障时,collect_repos 应该正常返回而不是崩")
    fetch_repos.requests.get = ssl_boom
    try:
        repos = daily_update.collect_repos()
        check("collect_repos 正常返回", True, f"(返回 {len(repos)} 个)")
    except BaseException as e:
        check("collect_repos 正常返回", False, f"抛了 {type(e).__name__} —— job 还是会死")

    print()
    if FAILED:
        print(f"❌ {len(FAILED)} 项失败:{', '.join(FAILED)}")
        sys.exit(1)
    print("✅ 全部通过")


if __name__ == "__main__":
    main()
