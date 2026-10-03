#!/usr/bin/env python3
"""回归测试:sync_all 的失败隔离 + 退出码分类。

要防住的两种错:

  ① **一个人失败拖垮所有人。**
     多用户之后,某个人的 token 过期是常态。如果没做隔离,
     一个过期 token 就让后面所有人的 star 都同步不上 ——
     而"别人的推荐页是空的"这种问题,没人会想到是另一个用户的 token 引起的。

  ② **把"重试没用"的失败当成"重试有用"。**
     最初写的规则是"全员失败 → 退出码 1 → 让定时任务重试"。
     但那把两种情况混成了一种:
        · 网络抖了      → 重试真的可能成功      → 该退 1
        · token 过期了  → 重试一百次也一样      → 该退 0
     混在一起的后果:一个过期的 token 让任务每天白重试三轮,
     日志里堆满同样的报错,真正的问题被埋掉。
     (这不是假想 —— 第一次真跑就撞上了:本机存的 token 确实已经失效。)

跑法:
    .venv/bin/python tests/test_sync_all.py
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
import sync_all
import sync_following
import sync_stars
from sync_common import SyncAuthError

FAILED = []


def check(name, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def make_db(tmpdir, users):
    """建一个只有 users 表的临时库。users 是 [(login, 有token)]。"""
    path = os.path.join(tmpdir, "t.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    db.DB_PATH = path
    with open(db.SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    for login, has_token in users:
        conn.execute("INSERT INTO users (login, token) VALUES (?, ?)",
                     (login, "tok-" + login if has_token else None))
    conn.commit()
    return conn


def fake(behavior):
    """behavior: login → None(成功) | "auth" | "net" """
    def sync_user(conn, user_id, quiet=False):
        login = conn.execute("SELECT login FROM users WHERE id=?",
                             (user_id,)).fetchone()["login"]
        act = behavior.get(login)
        if act == "auth":
            raise SyncAuthError("token 无效或已过期,重新登录一次")
        if act == "net":
            raise RuntimeError("连不上 GitHub:SSLError")
        return {"login": login, "fetched": 1, "written": 1, "total": 1}
    return sync_user


def run(tmpdir, users, behavior):
    make_db(tmpdir, users)
    sync_stars.sync_user = fake(behavior)
    sync_following.sync_user = fake(behavior)
    print()
    return sync_all.main()


def main():
    tmp = tempfile.mkdtemp()

    # ---- 1. 全部成功 → 0 ------------------------------------------------
    print("1. 所有人同步成功")
    code = run(os.path.join(tmp, "a"), [("alice", True), ("bob", True)], {})
    check("退出码 0", code == 0, f"(实际 {code})")

    # ---- 2. ★ 失败隔离:一个 token 过期,另一个照常同步 ------------------
    print("2. alice 的 token 过期,bob 应该照常同步上")
    seen = []
    make_db(os.path.join(tmp, "b"), [("alice", True), ("bob", True)])
    real_fake = fake({"alice": "auth"})

    def spy(conn, user_id, quiet=False):
        login = conn.execute("SELECT login FROM users WHERE id=?",
                             (user_id,)).fetchone()["login"]
        seen.append(login)
        return real_fake(conn, user_id, quiet)

    sync_stars.sync_user = spy
    sync_following.sync_user = spy
    code = sync_all.main()
    check("bob 也被同步到了(没被 alice 拖累)", "bob" in seen, f"(实际同步了 {seen})")
    check("退出码 0(个别人失败不该让整轮重做)", code == 0, f"(实际 {code})")

    # ---- 3. 全挂但都是 token 失效 → 0(重试没用,别白跑)-----------------
    print("3. 所有人 token 都失效 → 退出码应该是 0")
    code = run(os.path.join(tmp, "c"),
               [("alice", True), ("bob", True)],
               {"alice": "auth", "bob": "auth"})
    check("退出码 0(重试不会好)", code == 0, f"(实际 {code})")

    # ---- 4. 全挂且是网络问题 → 1(让任务重试)---------------------------
    print("4. 所有人都是网络失败 → 退出码应该是 1")
    code = run(os.path.join(tmp, "d"),
               [("alice", True), ("bob", True)],
               {"alice": "net", "bob": "net"})
    check("退出码 1(重试可能成功)", code == 1, f"(实际 {code})")

    # ---- 5. 混合:一个是 token 问题、一个是网络问题 → 该重试 -------------
    print("5. 一个 token 失效 + 一个网络失败 → 该重试")
    code = run(os.path.join(tmp, "e"),
               [("alice", True), ("bob", True)],
               {"alice": "auth", "bob": "net"})
    check("退出码 1(只要有一个像网络问题就值得重试)", code == 1, f"(实际 {code})")

    # ---- 6. 没有用户 → 0,不该报错 --------------------------------------
    print("6. 一个可同步的用户都没有")
    code = run(os.path.join(tmp, "f"), [("alice", False)], {})
    check("退出码 0", code == 0, f"(实际 {code})")

    print()
    if FAILED:
        print(f"❌ {len(FAILED)} 项失败:")
        for f in FAILED:
            print(f"     {f}")
        sys.exit(1)
    print("✅ 全部通过")


if __name__ == "__main__":
    main()
