#!/usr/bin/env python3
"""P2:数据库连接 + 写入(SQLite)。

这一层只干三件事,别的脚本 import 它,不要自己到处拼 SQL:
    get_conn()      拿一个连接
    init_db(conn)   按 schema.sql 建表
    upsert_repos()  把一批 repo 写进库(重复跑不会产生重复行 = 幂等)
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "repos.db")     # data/ 在 .gitignore 里,数据库不进 Git
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

# 列的顺序必须和下面 SQL 里的 ? 一一对应
COLUMNS = ["id", "full_name", "description", "language",
           "topics", "stargazers_count", "pushed_at", "html_url"]

# 一次写好、反复用。? 是占位符:值由 sqlite3 自己转义,不怕引号/注入
UPSERT_SQL = f"""
INSERT INTO repos ({", ".join(COLUMNS)})
VALUES ({", ".join(["?"] * len(COLUMNS))})
ON CONFLICT(full_name) DO UPDATE SET
    description      = excluded.description,
    language         = excluded.language,
    topics           = excluded.topics,
    stargazers_count = excluded.stargazers_count,
    pushed_at        = excluded.pushed_at,
    html_url         = excluded.html_url,
    fetched_at       = strftime('%Y-%m-%dT%H:%M:%SZ','now')
"""
# excluded = "这次想插进去的那一行"。所以冲突时 = 用新数据覆盖旧数据,
# 但 id / full_name(主键和身份)不动 —— 行的身份保持稳定,P3 的快照才能挂在它上面。
# 注意:ON CONFLICT(full_name) 只管 full_name 这个约束;万一 id 撞了(几乎不可能),
# 会直接抛 IntegrityError,这正是我们想要的——静默吞掉才危险。


# P3:快照的 upsert。同一个 repo 同一天再写一次 = 覆盖当天的值(所以当天重跑是安全的)
SNAPSHOT_SQL = """
INSERT INTO repo_snapshots (repo_id, snapshot_date, stargazers_count)
VALUES (?, ?, ?)
ON CONFLICT(repo_id, snapshot_date) DO UPDATE SET
    stargazers_count = excluded.stargazers_count
"""


def to_utc_iso(value):
    """把各种 ISO8601 时间统一成 UTC 的 ...Z 形式;空的/解析不了的返回 None。"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:                  # 没带时区就当它是 UTC,别拿本地时间硬凑
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_to_row(repo):
    """一个 JSON dict → 和 COLUMNS 对齐的 tuple。缺字段给安全的默认值,别让 None 炸掉。"""
    return (
        repo.get("id"),
        repo.get("full_name"),
        repo.get("description"),                          # 可能为 None,库里就是 NULL
        repo.get("language"),
        json.dumps(repo.get("topics") or [], ensure_ascii=False),   # list → JSON 字符串
        repo.get("stargazers_count") or 0,                # None/缺字段 → 0
        to_utc_iso(repo.get("pushed_at")),
        repo.get("html_url"),
    )


def get_conn():
    """打开连接。返回的 Row 支持 row["full_name"] 这种按列名取值。"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # 读写不互相卡住,以后接后端更顺
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn):
    """建表(已经建过就什么都不做 —— schema.sql 里全是 IF NOT EXISTS)。"""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def upsert_repos(conn, repos):
    """批量 upsert。返回 (读进来的条数, 实际落库的行数)。"""
    rows = [repo_to_row(r) for r in repos if r.get("full_name")]   # 没名字的直接丢
    before = conn.total_changes
    conn.executemany(UPSERT_SQL, rows)      # 一条 SQL 跑 N 次,比循环 execute 快得多
    conn.commit()
    return len(rows), conn.total_changes - before


def count_repos(conn):
    return conn.execute("SELECT COUNT(*) FROM repos").fetchone()[0]


def today_utc():
    """今天的 UTC 日期,格式 'YYYY-MM-DD'。
    全项目只用 UTC 一套口径 —— 别让"今天"在本地时区和 UTC 之间来回横跳。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def save_snapshots(conn, repos, snapshot_date):
    """给这批 repo 写指定日期的 star 快照。返回实际写入的行数。"""
    rows = [(r.get("id"), snapshot_date, r.get("stargazers_count") or 0)
            for r in repos if r.get("id")]
    before = conn.total_changes
    conn.executemany(SNAPSHOT_SQL, rows)
    conn.commit()
    return conn.total_changes - before


def snapshot_dates(conn):
    """库里出现过的快照日期,从新到旧。trending.py 靠它拿"最近的两个日期"。"""
    cur = conn.execute(
        "SELECT DISTINCT snapshot_date FROM repo_snapshots ORDER BY snapshot_date DESC")
    return [row[0] for row in cur]


def count_snapshots(conn):
    return conn.execute("SELECT COUNT(*) FROM repo_snapshots").fetchone()[0]


if __name__ == "__main__":
    c = get_conn()
    init_db(c)
    print(f"数据库:{DB_PATH}")
    print(f"repos 表现有 {count_repos(c)} 行")
    print(f"repo_snapshots 表现有 {count_snapshots(c)} 行")
