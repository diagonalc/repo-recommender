#!/usr/bin/env python3
"""检查:有没有任何一个接口会把用户的 GitHub token 泄出去。

做法很直接 —— 拿真 token 去**搜索每一个接口的响应体**。
比读代码可靠:代码里没有 `SELECT token` 不代表拼出来的字段里没有,
而漏出去的后果是"任何打开 F12 的人都能拿到你的 GitHub 授权"。

临时的,跑完就删(_*.py 已被 .gitignore 挡住)。
"""
import os
import sys
import urllib.error
import urllib.request

# 从 tests/ 里跑,得把仓库根目录加进 import 路径才找得到 db 等模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

conn = db.get_conn()
user = conn.execute("SELECT id, token FROM users ORDER BY id LIMIT 1").fetchone()
TOKEN = user["token"]
SID = conn.execute("SELECT token FROM sessions ORDER BY rowid DESC LIMIT 1").fetchone()[0]
BASE = "http://127.0.0.1:18080"

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

PATHS = [
    "/", "/index.html", "/app.js",
    "/api/me", "/api/me/starred", "/api/me/following", "/api/recommend",
    "/api/events", "/api/opinions", "/api/tags",
    "/api/repos?sort=stars&limit=5", "/api/repos?sort=trending&limit=5",
    "/api/search?q=react&scope=local", "/api/search?q=react&scope=github",
    "/api/repos/yt-dlp/yt-dlp",
    "/docs", "/openapi.json",
]

leaks = []
for p in PATHS:
    req = urllib.request.Request(BASE + p)
    req.add_header("Cookie", "repos_sid=" + SID)
    try:
        with opener.open(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"  ?  {p}  ({type(e).__name__})")
        continue
    hit = TOKEN in body
    print(f"  {'❌ 泄漏!' if hit else '✅'}  {p}  ({len(body)} 字节)")
    if hit:
        leaks.append(p)

print()
if leaks:
    print(f"❌ 这些接口把 token 泄出去了:{leaks}")
    sys.exit(1)
print("✅ 没有任何接口返回这个 token")
