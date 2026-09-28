#!/usr/bin/env python3
"""同步你关注的开发者(GitHub 的 following 列表)。

用法:
    .venv/bin/python sync_following.py

和 sync_stars.py 是一对:
    那个同步"你收藏了哪些仓库",这个同步"你关注了哪些人"。

读自己的关注列表用只读 token 就够,不需要额外权限 ——
(GitHub 的 URL 就叫 /user/following,直译就是"你关注的人"。)

幂等:重复跑不会产生重复行(靠 ON CONFLICT(login) 更新)。
"""
import time

import requests

from db import (count_following, get_conn, init_db, list_following,
                save_following)
from fetch_repos import TOKEN

URL = "https://api.github.com/user/following"
PER_PAGE = 100


def fetch_page(page):
    """拉一页。分页规则和别的接口一样:per_page + page,每页最多 100。"""
    headers = {"Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"token {TOKEN}"
    r = requests.get(URL, headers=headers,
                     params={"per_page": PER_PAGE, "page": page}, timeout=30)
    if r.status_code == 401:
        raise RuntimeError("token 无效或已过期,去设置页重新生成")
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def main():
    if not TOKEN:
        print("需要 token:/user/following 拉的是你自己的数据,未认证拿不到。")
        return

    users, page = [], 1
    while True:
        batch = fetch_page(page)
        if not batch:
            break
        users.extend(batch)
        print(f"  第 {page} 页 +{len(batch)}(累计 {len(users)})")
        if len(batch) < PER_PAGE:      # 不满一页 = 最后一页
            break
        page += 1
        time.sleep(1)

    if not users:
        print("你没有关注任何人。")
        return

    conn = get_conn()
    init_db(conn)
    written = save_following(conn, users)

    print(f"\n写入 {written} 条;following 表共 {count_following(conn)} 个")
    print("\n前 10 个:")
    for row in list_following(conn, 10):
        print(f"  {row['login']}" + (f"  ({row['name']})" if row["name"] else ""))


if __name__ == "__main__":
    main()
