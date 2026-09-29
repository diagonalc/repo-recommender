#!/usr/bin/env python3
"""同步某个用户的关注列表(GitHub 的 following)。

用法:
    .venv/bin/python sync_following.py              # 默认同步 1 号用户
    REPOS_USER=2 .venv/bin/python sync_following.py # 换个人

和 sync_stars.py 是一对:那个同步"收藏了哪些仓库",这个同步"关注了哪些人"。
token 也是用这个人登录时存下来的那个。
"""
import os
import time

import requests

from db import (count_following, get_conn, get_user, init_db, list_following,
                save_following, user_token)

URL = "https://api.github.com/user/following"
PER_PAGE = 100


def fetch_page(token, page):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    r = requests.get(URL, headers=headers,
                     params={"per_page": PER_PAGE, "page": page}, timeout=30)
    if r.status_code == 401:
        raise RuntimeError("token 无效或已过期,重新登录一次")
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

    print(f"同步 {user['login']} 的关注列表…")
    users, page = [], 1
    while True:
        batch = fetch_page(token, page)
        if not batch:
            break
        users.extend(batch)
        print(f"  第 {page} 页 +{len(batch)}(累计 {len(users)})")
        if len(batch) < PER_PAGE:
            break
        page += 1
        time.sleep(1)

    if not users:
        print("没有关注任何人。")
        return

    written = save_following(conn, user_id, users)
    print(f"\n写入 {written} 条;{user['login']} 共关注 {count_following(conn, user_id)} 个")
    print("\n前 10 个:")
    for row in list_following(conn, user_id, 10):
        print(f"  {row['login']}" + (f"  ({row['name']})" if row["name"] else ""))


if __name__ == "__main__":
    main()
