#!/usr/bin/env python3
"""P4:同步某个用户的 star 历史。

用法:
    .venv/bin/python sync_stars.py              # 默认同步 1 号用户
    REPOS_USER=2 .venv/bin/python sync_stars.py # 换个人

要**给所有人**同步,用 sync_all.py(每日定时任务跑的就是它)。

token 从哪来:登录时 GitHub 给的那个,**存在 users 表里**。
不再是全局的 GITHUB_TOKEN —— 多用户之后,每个人用自己的 token 拉自己的数据。

幂等:重复跑多少次,starred 行数都不变(靠 ON CONFLICT(user_id, repo_id) 覆盖)。
"""
import os
import time

from db import (count_starred, get_conn, get_user, init_db, recent_starred,
                save_starred, set_token_status, upsert_repos, user_token)
from sync_common import SyncAuthError
from sync_common import fetch_page as _fetch

URL = "https://api.github.com/user/starred"
PER_PAGE = 100


def fetch_page(token, page):
    """拉一页 star。带 star+json 才有真实的 star 时间。

    错误处理在 sync_common.fetch_page 里(网络错误 → RuntimeError,
    token 失效 → SyncAuthError),和 sync_following 共用同一份。
    """
    return _fetch(URL, token, page, PER_PAGE,
                  accept="application/vnd.github.star+json")


def sync_user(conn, user_id, quiet=False):
    """同步一个人的 star 历史。返回结果摘要 dict。

    ⚠️ **失败就抛 RuntimeError,不要吞掉。**
    调用方(每日任务)必须知道"这个人没同步成功" ——
    静默失败会让"推荐页永远是空的"变成一个没人解释得清的现象,
    而原因其实只是某个人的 token 过期了。
    """
    def say(*args):
        if not quiet:
            print(*args)

    user = get_user(conn, user_id)
    if not user:
        raise RuntimeError(f"没有 id={user_id} 的用户")

    token = user_token(conn, user_id)
    if not token:
        raise RuntimeError(f"{user['login']} 没有可用的 token(退出后重新登录一次)")

    say(f"同步 {user['login']} 的 star 历史…")
    try:
        items, page = [], 1
        while True:
            batch = fetch_page(token, page)
            if not batch:
                break
            items.extend(batch)
            say(f"  第 {page} 页 +{len(batch)}(累计 {len(items)})")
            if len(batch) < PER_PAGE:  # 不满一页 = 最后一页
                break
            page += 1
            time.sleep(1)
    except SyncAuthError:
        # 这个人的 token 废了。记下来,前端才能提示他去重新登录 ——
        # 不然这件事只存在于日志里,他只会觉得"这站坏了"。
        # 记完继续往上抛:调用方也要知道这次没成功。
        set_token_status(conn, user_id, False)
        raise

    # 走完说明 token 是好用的(哪怕一个 star 都没有 —— 请求本身成功了)。
    set_token_status(conn, user_id, True)

    written = 0
    if items:
        repos = [it["repo"] for it in items if it.get("repo")]
        upsert_repos(conn, repos)      # starred 有外键指向 repos,先把元数据落库
        written = save_starred(conn, user_id, items)

    total = count_starred(conn, user_id)
    say(f"  {user['login']}:拉到 {len(items)} 个,落库 {written} 行,共 {total} 个")
    return {"login": user["login"], "fetched": len(items),
            "written": written, "total": total}


def main():
    conn = get_conn()
    init_db(conn)

    user_id = int(os.environ.get("REPOS_USER", "1"))
    try:
        sync_user(conn, user_id)
    except RuntimeError as e:
        print(e)
        return

    print("\n最近 10 个 star(按 star 时间倒序):")
    for row in recent_starred(conn, user_id, 10):
        when = (row["starred_at"] or "时间未知")[:10]
        print(f"  {when}  {row['full_name']}  ({row['language']})  ★{row['stargazers_count']}")


if __name__ == "__main__":
    main()
