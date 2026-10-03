#!/usr/bin/env python3
"""回归测试:会话 cookie 的 Secure 标志算得对不对。

**为什么这个 5 行的函数值得单独测:**
    算错的后果是两头的,而且都很严重:
      · 该加没加   → cookie 会跟着明文 http 请求发出去,等于白搭 HTTPS
      · 不该加却加 → 浏览器直接**丢掉**这个 cookie,本机 http 调试时
                     "怎么登都登不上",而且没有任何报错,极难排查

    而这里最容易错的恰恰是判断依据:看起来该用 request.url.scheme,
    但 cloudflared 是直连 localhost 的,**本地那一跳永远是 http** ——
    从请求本身根本看不出用户实际走的是 https。
    (同一个坑在 redirect_uri 上已经栽过一次,那次表现为登录报
     redirect_uri mismatch。)

跑法:
    .venv/bin/python tests/test_cookie_secure.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api
import auth

FAILED = []
_SAVED = auth.PUBLIC_BASE


class FakeURL:
    def __init__(self, host):
        self.hostname = host


class FakeRequest:
    def __init__(self, host):
        self.url = FakeURL(host)


def check(name, ok, detail=""):
    print(f"  {'ok ' if ok else 'FAIL'} {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def probe(base, host):
    auth.PUBLIC_BASE = base
    return api.cookie_secure(FakeRequest(host))


CASES = [
    # (公开地址, 请求的 host, 期望, 说明)
    ("https://diagonalc.dpdns.org", "diagonalc.dpdns.org",
     True,  "线上走 https —— 该加"),
    ("https://diagonalc.dpdns.org", "127.0.0.1",
     False, "配了 https,但从本机访问 —— 加了就登不上"),
    ("https://diagonalc.dpdns.org", "localhost",
     False, "同上(localhost)"),
    ("", "127.0.0.1",
     False, "本地开发,没配公开地址"),
    ("http://192.168.1.5:18080", "192.168.1.5",
     False, "局域网纯 http —— 加了就登不上"),
]


def main():
    print("cookie_secure 在各场景下的判断\n")
    for base, host, want, note in CASES:
        got = probe(base, host)
        check(f"{note}", got == want, f"(host={host} → Secure={got})")

    auth.PUBLIC_BASE = _SAVED      # 别把模块状态留给别人(虽然这是独立进程)

    print()
    if FAILED:
        print(f"{len(FAILED)} 项失败")
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main()
