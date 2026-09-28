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
ON CONFLICT(id) DO UPDATE SET
    full_name        = excluded.full_name,
    description      = excluded.description,
    language         = excluded.language,
    topics           = excluded.topics,
    stargazers_count = excluded.stargazers_count,
    pushed_at        = excluded.pushed_at,
    html_url         = excluded.html_url,
    fetched_at       = strftime('%Y-%m-%dT%H:%M:%SZ','now')
"""
# excluded = "这次想插进去的那一行"。所以冲突时 = 用新数据覆盖旧数据。
#
# 冲突目标选 id,而不是 full_name —— 这是实跑六天后被真实数据打脸改的:
#   repo 会改名、换 owner。这时 id 不变、full_name 变了。若按 full_name 判断冲突,
#   库里那行(id 相同、旧名字)和新数据(id 相同、新名字)会被当成两行,
#   插入时撞上 id 主键约束 → IntegrityError,整批数据一行都写不进去。
# 所以定下来:id 是身份(它永不变,所以拿它当主键),full_name 只是普通字段,跟着更新。
# 这也是当初把 id 设成主键、让快照挂在 repo_id 上的回报 —— 改名不断历史。
#
# 另一面:若新数据的 full_name 撞上了"另一个 id"的行(旧 repo 被删、名字被别人抢走),
# 仍然会抛 IntegrityError —— 这种真异常就该炸出来,别静默吞。


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


# ---------------- P4:star 历史 + 行为事件 ----------------

# starred 是"状态表":一个 repo 一行。重复同步 = 覆盖时间,不会长出第二行。
STARRED_SQL = """
INSERT INTO starred (repo_id, starred_at)
VALUES (?, ?)
ON CONFLICT(repo_id) DO UPDATE SET
    starred_at = excluded.starred_at
"""

# events 是"流水表":只追加,永远不更新、不覆盖
EVENT_SQL = "INSERT INTO events (repo_id, action) VALUES (?, ?)"
EVENT_ACTIONS = ("interested", "not_interested")


def save_starred(conn, items):
    """items = /user/starred 的返回:[{"starred_at": ..., "repo": {...}}, ...]。

    返回写入行数。starred_at 可能是 None(没带 star+json 头),照存不误。
    """
    rows = []
    for it in items:
        repo = it.get("repo") or {}
        if repo.get("id"):
            rows.append((repo["id"], to_utc_iso(it.get("starred_at"))))
    before = conn.total_changes
    conn.executemany(STARRED_SQL, rows)
    conn.commit()
    return conn.total_changes - before


def count_starred(conn):
    return conn.execute("SELECT COUNT(*) FROM starred").fetchone()[0]


def recent_starred(conn, limit=10):
    """按 star 时间倒序 —— 这就是"我记得我 star 过什么"的查询。"""
    return conn.execute("""
        SELECT r.full_name, r.language, r.stargazers_count, s.starred_at
        FROM starred AS s
        JOIN repos   AS r ON r.id = s.repo_id
        ORDER BY s.starred_at DESC
        LIMIT ?""", (limit,)).fetchall()


def add_event(conn, repo_id, action):
    """记一条反馈。action 只能是 interested / not_interested(和表上的 CHECK 一致)。"""
    if action not in EVENT_ACTIONS:
        raise ValueError(f"action 只能是 {EVENT_ACTIONS},收到 {action!r}")
    conn.execute(EVENT_SQL, (repo_id, action))
    conn.commit()


def count_events(conn):
    return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]


def recent_events(conn, limit=10):
    return conn.execute("""
        SELECT e.id, e.action, e.created_at, r.full_name
        FROM events AS e
        LEFT JOIN repos AS r ON r.id = e.repo_id
        ORDER BY e.id DESC
        LIMIT ?""", (limit,)).fetchall()


# "当前态度" = 每个 repo 最后一条事件。
# 事件表是流水(只追加、不改不删),所以"改主意"就再写一条 —— 历史留全,
# 而"现在到底是什么态度"用 id 最大的那条回答。
_LATEST_OPINION_SQL = """
SELECT e.repo_id, e.action
FROM events AS e
WHERE e.id = (SELECT MAX(id) FROM events WHERE repo_id = e.repo_id)
"""


def latest_opinions(conn):
    """{repo_id: action} —— 每个 repo 当前的最终态度(最新一条说了算)。"""
    return {row["repo_id"]: row["action"] for row in conn.execute(_LATEST_OPINION_SQL)}


def opinion_map(conn):
    """{full_name: action} —— 给前端标按钮状态用。"""
    return {row["full_name"]: row["action"] for row in conn.execute(f"""
        SELECT r.full_name, e.action
        FROM events AS e JOIN repos AS r ON r.id = e.repo_id
        WHERE e.id = (SELECT MAX(id) FROM events WHERE repo_id = e.repo_id)""")}


# ---------------- P5:给 API 用的查询 ----------------

# 对外返回的列。集中写一处,免得每个接口各写一份列名(改字段时只改这里)
API_COLS = ("id, full_name, description, language, topics, "
            "stargazers_count, pushed_at, html_url")


def list_by_stars(conn, lang=None, limit=30):
    """按 star 数排行的候选池。给了 lang 就只挑那个语言。"""
    if lang:
        return conn.execute(
            f"SELECT {API_COLS} FROM repos WHERE language = ? "
            "ORDER BY stargazers_count DESC LIMIT ?", (lang, limit)).fetchall()
    return conn.execute(
        f"SELECT {API_COLS} FROM repos "
        "ORDER BY stargazers_count DESC LIMIT ?", (limit,)).fetchall()


GROWTH_SQL = """
SELECT r.id,
       r.full_name,
       r.description,
       r.language,
       r.html_url,
       cur.stargazers_count                          AS stars,
       prev.stargazers_count                         AS prev_stars,
       cur.stargazers_count - prev.stargazers_count  AS delta
FROM repo_snapshots AS cur
JOIN repo_snapshots AS prev ON prev.repo_id = cur.repo_id
JOIN repos          AS r    ON r.id = cur.repo_id
WHERE cur.snapshot_date  = ?
  AND prev.snapshot_date = ?
"""


def growth_rows(conn, cur_day, prev_day):
    """两个快照日之间、每个 repo 的 star 增量。

    这段 SQL 放在 db.py 而不是 trending.py,是为了让 trending.py(命令行)
    和 api.py(HTTP)共用同一份查询 —— 两处各写一份,早晚会写歪。
    """
    return conn.execute(GROWTH_SQL, (cur_day, prev_day)).fetchall()


def get_repo(conn, full_name):
    return conn.execute(f"SELECT {API_COLS} FROM repos WHERE full_name = ?",
                        (full_name,)).fetchone()


def repo_history(conn, repo_id):
    """某个 repo 的全部 star 快照(按日期升序)—— 详情页画曲线用。"""
    return conn.execute(
        "SELECT snapshot_date, stargazers_count FROM repo_snapshots "
        "WHERE repo_id = ? ORDER BY snapshot_date", (repo_id,)).fetchall()


def starred_list(conn, limit=200):
    return conn.execute("""
        SELECT r.id, r.full_name, r.description, r.language, r.html_url,
               r.stargazers_count, s.starred_at
        FROM starred AS s JOIN repos AS r ON r.id = s.repo_id
        ORDER BY s.starred_at DESC LIMIT ?""", (limit,)).fetchall()


def find_repo_id(conn, full_name):
    row = conn.execute("SELECT id FROM repos WHERE full_name = ?",
                       (full_name,)).fetchone()
    return row["id"] if row else None


# ---------------- P6:README 文本 ----------------

README_SQL = """
INSERT INTO readmes (repo_id, content)
VALUES (?, ?)
ON CONFLICT(repo_id) DO UPDATE SET
    content    = excluded.content,
    fetched_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
"""


def save_readme(conn, repo_id, content):
    conn.execute(README_SQL, (repo_id, content))
    conn.commit()


def repos_missing_readme(conn, limit=5000):
    """还没抓过 README 的 repo,按 star 从高到低 —— 先抓热门,冷门的相似度没人看。"""
    return conn.execute("""
        SELECT r.id, r.full_name
        FROM repos AS r
        LEFT JOIN readmes AS m ON m.repo_id = r.id
        WHERE m.repo_id IS NULL
        ORDER BY r.stargazers_count DESC
        LIMIT ?""", (limit,)).fetchall()


def repos_for_readme(conn, limit=5000, refresh=False):
    """要抓 README 的 repo,按 star 从高到低。

    refresh=False 只挑还没抓过的(日常增量跑);
    refresh=True  全部重抓 —— 改了 clean() 的清洗规则之后,得把旧的覆盖掉。
    """
    if refresh:
        return conn.execute(
            "SELECT id, full_name FROM repos ORDER BY stargazers_count DESC LIMIT ?",
            (limit,)).fetchall()
    return repos_missing_readme(conn, limit)


def count_readmes(conn):
    return conn.execute("SELECT COUNT(*) FROM readmes").fetchone()[0]


def readme_map(conn):
    """{repo_id: 文本} —— features.py 一次性取出来拼语料,别在循环里一条条查。"""
    return {row["repo_id"]: row["content"] or ""
            for row in conn.execute("SELECT repo_id, content FROM readmes")}


def readmes_for(conn, repo_ids):
    """{repo_id: 文本},只取指定的这几个 —— 出接口时用,别把整张表拉进内存。"""
    if not repo_ids:
        return {}
    marks = ",".join("?" * len(repo_ids))
    return {row["repo_id"]: row["content"] or "" for row in conn.execute(
        f"SELECT repo_id, content FROM readmes WHERE repo_id IN ({marks})",
        tuple(repo_ids))}


def repo_readme(conn, repo_id):
    row = conn.execute("SELECT content FROM readmes WHERE repo_id = ?",
                       (repo_id,)).fetchone()
    return (row["content"] or "") if row else ""


def repo_delta(conn, repo_id):
    """最近两个快照日之间这个 repo 的 star 增量;快照不足两份就返回 None。"""
    rows = conn.execute("""
        SELECT stargazers_count FROM repo_snapshots
        WHERE repo_id = ? ORDER BY snapshot_date DESC LIMIT 2""", (repo_id,)).fetchall()
    if len(rows) < 2:
        return None
    return rows[0]["stargazers_count"] - rows[1]["stargazers_count"]


def starred_at_of(conn, repo_id):
    """我什么时候 star 的它;没 star 过返回 None。"""
    row = conn.execute("SELECT starred_at FROM starred WHERE repo_id = ?",
                       (repo_id,)).fetchone()
    return row["starred_at"] if row else None


if __name__ == "__main__":
    c = get_conn()
    init_db(c)
    print(f"数据库:{DB_PATH}")
    print(f"repos 表现有 {count_repos(c)} 行")
    print(f"repo_snapshots 表现有 {count_snapshots(c)} 行")
    print(f"starred        表现有 {count_starred(c)} 行")
    print(f"events         表现有 {count_events(c)} 行")
