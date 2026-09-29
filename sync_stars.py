#!/usr/bin/env python3
"""P4:同步某个用户的 star 历史。

用法:
    .venv/bin/python sync_stars.py              # 默认同步 1 号用户
    REPOS_USER=2 .venv/bin/python sync_stars.py # 换个人

token 从哪来:登录时 GitHub 给的那个,**存在 users 表里**。
不再是全局的 GITHUB_TOKEN —— 多用户之后,每个人用自己的 token 拉自己的数据。

幂等:重复跑多少次,starred 行数都不变(靠 ON CONFLICT(user_id, repo_id) 覆盖)。
"""
import os
import time

import requests

from db import (count_starred, get_conn, get_user, init_db, recent_starred,
                save_starred, upsert_repos, user_token)

URL = "https://api.github.com/user/starred"
PER_PAGE = 100


def fetch_page(token, page):
    """拉一页 star。带 star+json 才有真实 star 时间。"""
    headers = {"Accept": "application/vnd.github.star+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    r = requests.get(URL, headers=headers,
                     params={"per_page": PER_PAGE, "page": page}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def main():
    conn = get_conn()
    init_db(conn)

    user_id = int(os.environ.get("REPOS_USER", "1"))
    user = get_user(conn, user_id)
    if not user:
        print(f"没有 id={user_id} 的用户 —— 先在网页上用 GitHub 登录一次")
        return

    token = user_token(conn, user_id)
    if not token:
        print(f"{user['login']} 没有可用的 token,退出后重新登录一次")
        return

    print(f"同步 {user['login']} 的 star 历史…")
    items, page = [], 1
    while True:
        batch = fetch_page(token, page)
        if not batch:
            break
        items.extend(batch)
        print(f"  第 {page} 页 +{len(batch)}(累计 {len(items)})")
        if len(batch) < PER_PAGE:      # 不满一页 = 最后一页
            break
        page += 1
        time.sleep(1)

    if not items:
        print("还没有 star 过任何 repo。")
        return

    repos = [it["repo"] for it in items if it.get("repo")]
    upsert_repos(conn, repos)          # 先把 repo 元数据落库(starred 有外键指向它)
    written = save_starred(conn, user_id, items)

    print(f"\nstar 落库 {written} 行;{user['login']} 共 {count_starred(conn, user_id)} 个")
    print("\n最近 10 个 star(按 star 时间倒序):")
    for row in recent_starred(conn, user_id, 10):
        when = (row["starred_at"] or "时间未知")[:10]
        print(f"  {when}  {row['full_name']}  ({row['language']})  ★{row['stargazers_count']}")


if __name__ == "__main__":
    main()
