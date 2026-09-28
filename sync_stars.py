#!/usr/bin/env python3
"""P4:同步你自己的 star 历史。

用法:
    python3 sync_stars.py

关键点:请求头带 Accept: application/vnd.github.star+json,
GitHub 才会把 star 时间(starred_at)一起给你。
不带这个头,返回的只有 repo 元数据,时间就丢了 —— 而"什么时候 star 的",
正是以后算"口味随时间怎么变"的依据。

幂等:重复跑多少次,starred 表行数都不变(靠 ON CONFLICT(repo_id) 覆盖)。
"""
import time

import requests

from db import (count_repos, count_starred, get_conn, init_db,
                recent_starred, save_starred, upsert_repos)
from fetch_repos import TOKEN

URL = "https://api.github.com/user/starred"
PER_PAGE = 100


def fetch_page(page):
    """拉一页 star。分页规则和 search 一样:per_page + page,每页最多 100。"""
    headers = {"Accept": "application/vnd.github.star+json"}
    if TOKEN:
        headers["Authorization"] = f"token {TOKEN}"
    r = requests.get(URL, headers=headers,
                     params={"per_page": PER_PAGE, "page": page}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def main():
    if not TOKEN:
        print("需要 token:/user/starred 拉的是「你」的数据,未认证拿不到。")
        return

    items = []
    page = 1
    while True:
        batch = fetch_page(page)
        if not batch:
            break
        items.extend(batch)
        print(f"  第 {page} 页 +{len(batch)}(累计 {len(items)})")
        if len(batch) < PER_PAGE:      # 不满一页 = 已经到最后一页了
            break
        page += 1
        time.sleep(1)

    if not items:
        print("你还没有 star 过任何 repo。")
        return

    repos = [it["repo"] for it in items if it.get("repo")]

    conn = get_conn()
    init_db(conn)
    upsert_repos(conn, repos)          # 先把 repo 元数据落库(starred 有外键指向 repos.id)
    written = save_starred(conn, items)

    print(f"\nstar 落库 {written} 行;starred 表共 {count_starred(conn)} 行")
    print(f"repos 表共 {count_repos(conn)} 行")

    print("\n最近 10 个 star(按 star 时间倒序):")
    for row in recent_starred(conn, 10):
        when = (row["starred_at"] or "时间未知")[:10]
        print(f"  {when}  {row['full_name']}  ({row['language']})  ★{row['stargazers_count']}")


if __name__ == "__main__":
    main()
