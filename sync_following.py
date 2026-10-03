#!/usr/bin/env python3
"""同步某个用户的关注列表(GitHub 的 following)。

用法:
    .venv/bin/python sync_following.py              # 默认同步 1 号用户
    REPOS_USER=2 .venv/bin/python sync_following.py # 换个人

要**给所有人**同步,用 sync_all.py(每日定时任务跑的就是它)。

和 sync_stars.py 是一对:那个同步"收藏了哪些仓库",这个同步"关注了哪些人"。
token 也是用这个人登录时存下来的那个。
"""
import os
import time

from db import (count_following, get_conn, get_user, init_db, list_following,
                save_following, set_token_status, user_token)
from sync_common import SyncAuthError
from sync_common import fetch_page as _fetch

URL = "https://api.github.com/user/following"
PER_PAGE = 100


def fetch_page(token, page):
    """拉一页关注。错误处理与 sync_stars 共用同一份(sync_common.fetch_page)。"""
    return _fetch(URL, token, page, PER_PAGE)


def sync_user(conn, user_id, quiet=False):
    """同步一个人的关注列表。返回结果摘要 dict。失败抛 RuntimeError(见 sync_stars)。"""
    def say(*args):
        if not quiet:
            print(*args)

    user = get_user(conn, user_id)
    if not user:
        raise RuntimeError(f"没有 id={user_id} 的用户")

    token = user_token(conn, user_id)
    if not token:
        raise RuntimeError(f"{user['login']} 没有可用的 token(退出后重新登录一次)")

    say(f"同步 {user['login']} 的关注列表…")
    try:
        users, page = [], 1
        while True:
            batch = fetch_page(token, page)
            if not batch:
                break
            users.extend(batch)
            say(f"  第 {page} 页 +{len(batch)}(累计 {len(users)})")
            if len(batch) < PER_PAGE:
                break
            page += 1
            time.sleep(1)
    except SyncAuthError:
        # token 废了 —— 记下来好让前端提示(见 sync_stars 里同样的处理)
        set_token_status(conn, user_id, False)
        raise

    set_token_status(conn, user_id, True)

    written = save_following(conn, user_id, users) if users else 0
    total = count_following(conn, user_id)
    say(f"  {user['login']}:拉到 {len(users)} 个,写入 {written} 条,共 {total} 个")
    return {"login": user["login"], "fetched": len(users),
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

    print("\n前 10 个:")
    for row in list_following(conn, user_id, 10):
        print(f"  {row['login']}" + (f"  ({row['name']})" if row["name"] else ""))


if __name__ == "__main__":
    main()
