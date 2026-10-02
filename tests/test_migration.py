#!/usr/bin/env python3
"""回归测试:数据库迁移必须**可重入**(中断之后下一次启动还能接着升)。

背景 —— 这是审查时发现的一个"错了就永久坏掉"的 bug:

    _migrate_multiuser 原来在开头有个总闸门:
        cols = _table_columns(conn, "starred")
        if not cols or "user_id" in cols:
            return
    它拿 starred 一张表的状态,决定**整段**迁移要不要跑。
    但 starred / following / events / comments 是四次各自独立落地的操作。

    于是:进程如果在"starred 升完了、following 还没升"之间被杀掉
    (崩溃 / OOM / 被 kill / 两个进程同时 init_db),
    下次启动时 starred 已经有 user_id → 总闸门放行 → following 永远升不了。
    之后 list_following / add_event 全报 "no such column: user_id",一路 500,
    而且**再也不会自愈** —— 让它们坏掉的那个判断,同时也挡住了修复。

    修法:去掉总闸门,让每张表自己判断。

跑法:
    .venv/bin/python tests/test_migration.py
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

FAILED = []


def check(name, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


# 单用户时代的表结构(user_id 之前的样子),用 sqlite_master 里的**原始文本**建,
# 这样 _migrate_events 的 "neutral" in sql 判断才和真实场景一致。
OLD_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gh_id INTEGER UNIQUE, login TEXT NOT NULL, name TEXT,
    avatar_url TEXT, token TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE repos (
    id INTEGER PRIMARY KEY, full_name TEXT NOT NULL UNIQUE, description TEXT,
    language TEXT, topics TEXT, stargazers_count INTEGER NOT NULL DEFAULT 0,
    pushed_at TEXT, html_url TEXT,
    fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE starred (
    repo_id INTEGER NOT NULL, starred_at TEXT,
    first_seen TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (repo_id)
);
CREATE TABLE following (
    login TEXT NOT NULL, name TEXT, avatar_url TEXT, html_url TEXT,
    first_seen TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (login)
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, repo_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('interested','not_interested')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, repo_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    author TEXT
);
"""

SEED = """
INSERT INTO repos (id, full_name) VALUES (1, 'owner/repo1'), (2, 'owner/repo2');
INSERT INTO starred (repo_id, starred_at) VALUES (1, '2026-01-01T00:00:00Z');
INSERT INTO following (login, name) VALUES ('someone', 'Some One');
INSERT INTO events (repo_id, action) VALUES (1, 'interested');
INSERT INTO comments (repo_id, body) VALUES (1, 'hello');
"""


def fresh_db(tmpdir, half_migrated=False):
    """建一个临时库。half_migrated=True 时模拟"升了一半就崩了"的状态:
    starred 已经升好(有 user_id),following/events/comments 还没升。"""
    path = os.path.join(tmpdir, "t.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(OLD_SCHEMA)
    conn.executescript(SEED)

    if half_migrated:
        # 手动把 starred 升级成新版(模拟那次中断停在这里)
        conn.executescript("""
            CREATE TABLE users2 (id INTEGER PRIMARY KEY AUTOINCREMENT, gh_id INTEGER,
                login TEXT NOT NULL, name TEXT, avatar_url TEXT, token TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
            DROP TABLE users;
            ALTER TABLE users2 RENAME TO users;
            INSERT INTO users (id, login) VALUES (1, 'me');
            ALTER TABLE starred RENAME TO starred_old;
            CREATE TABLE starred (
                user_id INTEGER NOT NULL, repo_id INTEGER NOT NULL, starred_at TEXT,
                first_seen TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                PRIMARY KEY (user_id, repo_id)
            );
            INSERT INTO starred (user_id, repo_id, starred_at, first_seen)
                SELECT 1, repo_id, starred_at, first_seen FROM starred_old;
            DROP TABLE starred_old;
        """)
    conn.commit()
    # 让 db 模块用这个临时库
    db.DB_PATH = path
    return conn


def cols(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def main():
    tmpdir = tempfile.mkdtemp()

    # ---- 场景 1:完整的单用户库 → 一把升完,数据一条不少 -----------------
    print("1. 单用户库正常升级")
    conn = fresh_db(os.path.join(tmpdir, "a"))
    db.init_db(conn)
    for t in ("starred", "following", "events", "comments"):
        check(f"{t} 有 user_id", "user_id" in cols(conn, t))
    check("starred 数据还在", conn.execute("SELECT COUNT(*) FROM starred").fetchone()[0] == 1)
    check("following 数据还在", conn.execute("SELECT COUNT(*) FROM following").fetchone()[0] == 1)
    check("events 数据还在", conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1)
    check("comments 数据还在", conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0] == 1)
    check("老数据归给了 user_id=1",
          conn.execute("SELECT COUNT(*) FROM events WHERE user_id=1").fetchone()[0] == 1)
    check("events 现在允许 neutral",
          "neutral" in conn.execute(
              "SELECT sql FROM sqlite_master WHERE name='events'").fetchone()["sql"])

    # ---- 场景 2:★ 核心回归 —— 升了一半就崩,下次启动必须能自愈 ----------
    print("\n2. 半迁移状态(上次升到 starred 就被杀了)→ 重启后要能补完")
    conn2 = fresh_db(os.path.join(tmpdir, "b"), half_migrated=True)
    before = cols(conn2, "following")
    check("前提:following 确实还没升", "user_id" not in before, f"(列={sorted(before)})")

    db.init_db(conn2)          # ← 这以前会被总闸门挡住,什么都不做

    for t in ("starred", "following", "events", "comments"):
        check(f"{t} 补上了 user_id", "user_id" in cols(conn2, t))
    check("following 数据没丢",
          conn2.execute("SELECT COUNT(*) FROM following").fetchone()[0] == 1)
    check("events 数据没丢",
          conn2.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1)
    check("starred 没被重复迁移(还是 1 行)",
          conn2.execute("SELECT COUNT(*) FROM starred").fetchone()[0] == 1)

    # ---- 场景 3:反复跑 init_db 应该是幂等的 -----------------------------
    print("\n3. 连跑 3 次 init_db(幂等性)")
    conn3 = fresh_db(os.path.join(tmpdir, "c"))
    for _ in range(3):
        db.init_db(conn3)
    check("starred 还是 1 行", conn3.execute("SELECT COUNT(*) FROM starred").fetchone()[0] == 1)
    check("events 还是 1 行", conn3.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1)
    check("没有多出占位用户", conn3.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1,
          f"(users={conn3.execute('SELECT COUNT(*) FROM users').fetchone()[0]})")

    # ---- 场景 4:全新库(用 schema.sql)不该造出占位用户 -----------------
    print("\n4. 全新空库(直接吃 schema.sql)")
    path4 = os.path.join(tmpdir, "d", "t.db")
    os.makedirs(os.path.dirname(path4), exist_ok=True)
    db.DB_PATH = path4
    conn4 = sqlite3.connect(path4)
    conn4.row_factory = sqlite3.Row
    db.init_db(conn4)
    n_users = conn4.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    check("没有凭空多出 'me' 占位用户", n_users == 0, f"(users={n_users})")

    print()
    if FAILED:
        print(f"❌ {len(FAILED)} 项失败:")
        for f in FAILED:
            print(f"     {f}")
        sys.exit(1)
    print("✅ 全部通过")


if __name__ == "__main__":
    main()
