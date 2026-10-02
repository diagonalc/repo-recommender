#!/usr/bin/env python3
"""P2:数据库连接 + 写入(SQLite)。

这一层只干三件事,别的脚本 import 它,不要自己到处拼 SQL:
    get_conn()      拿一个连接
    init_db(conn)   按 schema.sql 建表
    upsert_repos()  把一批 repo 写进库(重复跑不会产生重复行 = 幂等)
"""
import json
import os
import secrets
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


def _migrate_events(conn):
    """把老的 events 表升级到允许 'neutral'。

    为什么要重建表:SQLite 不支持修改已有的 CHECK 约束,只能
    "改名 → 建新表 → 搬数据 → 删旧表"。这是它改约束的标准做法。

    只在检测到旧约束时才动,正常情况一行都不改。
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='events'").fetchone()
    if not row or not row["sql"] or "neutral" in row["sql"]:
        return

    # 重建时如果老表已经有 user_id,必须把它一起搬过去。
    #
    # 不搬的后果很隐蔽:所有表态会**静默地变成无主数据** ——
    # 之后 latest_opinions 查 "WHERE user_id = ?" 一条都匹配不到,
    # 推荐会把你的口味当成空的,而且不报任何错。
    # 正常情况下不会走到这儿(多用户迁移在后、每次启动都会先跑本函数),
    # 但"半迁移状态"下这是唯一能保住数据的地方,成本也就一行判断。
    has_user = "user_id" in _table_columns(conn, "events")
    user_col = "user_id     INTEGER," if has_user else ""
    col_list = "id, repo_id, user_id, action, created_at" if has_user else \
               "id, repo_id, action, created_at"

    conn.executescript(f"""
        ALTER TABLE events RENAME TO events_old;
        CREATE TABLE events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id     INTEGER NOT NULL,
            {user_col}
            action      TEXT NOT NULL
                        CHECK (action IN ('interested','not_interested','neutral')),
            created_at  TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            FOREIGN KEY (repo_id) REFERENCES repos(id)
        );
        INSERT INTO events ({col_list}) SELECT {col_list} FROM events_old;
        DROP TABLE events_old;
        CREATE INDEX IF NOT EXISTS idx_events_repo   ON events(repo_id);
        CREATE INDEX IF NOT EXISTS idx_events_action ON events(action);
    """)
    conn.commit()
    print("[migrate] events 表已重建,现在支持 neutral(取消表态)")


def _table_columns(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def ensure_local_user(conn):
    """保证有一个"我"的占位用户,返回它的 id。

    升级场景:老库里的 star / 关注 / 表态都是单用户的,没有"谁"这一列。
    迁移时把它们全归给这个占位用户。等你第一次用 GitHub 登录,
    会自动认领它(见 upsert_user),历史就接上了 —— 不用手工搬数据。
    """
    row = conn.execute(
        "SELECT id FROM users WHERE gh_id IS NULL ORDER BY id LIMIT 1").fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO users (login) VALUES ('me')")
    conn.commit()
    return cur.lastrowid


def upsert_user(conn, gh):
    """按 GitHub 身份找用户,没有就新建。返回 (user_id, 是否新建)。

    gh 形如 {id, login, name, avatar_url, token}。
    """
    row = conn.execute("SELECT id FROM users WHERE gh_id = ?",
                       (gh.get("id"),)).fetchone()
    if row:
        conn.execute("""UPDATE users SET login=?, name=?, avatar_url=?, token=?
                        WHERE id=?""",
                     (gh.get("login"), gh.get("name"), gh.get("avatar_url"),
                      gh.get("token"), row["id"]))
        conn.commit()
        return row["id"], False

    # 没有这个人 —— 看看有没有等着被认领的占位用户(单用户升级上来的那种)。
    #
    # ⚠️ 只在这个占位用户是**全表唯一一个用户**时才认领。
    #
    # 为什么加这个限制:占位用户身上挂着原单用户库的全部私有数据
    # (star 列表、关注列表、表态历史,以及由它们算出来的推荐)。
    # 原来的自动认领是**无条件**的,等于"谁先完成 GitHub 登录,谁就继承这些"。
    # 自己一个人用永远碰不到;但这站现在是对公网开放的,
    # 第一个登录的陌生人就会拿到站长的整个口味画像。
    #
    # 加"它是唯一用户"这个条件,能把窗口收窄到最小:
    # 那只可能出现在"老库刚升级完、还没有任何人登录过"的那一小段时间。
    # 站上有了第二个用户之后,这个分支就再也不会触发了。
    #
    # (注:这仍然不是万无一失 —— 真正的修法是校验"登录的人就是站长",
    #  但那需要把站长的 GitHub id 配进来。当前规模下不值得,先收窄。)
    ph = conn.execute(
        "SELECT id FROM users WHERE gh_id IS NULL ORDER BY id LIMIT 1").fetchone()
    if ph and conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1:
        print(f"[user] 认领占位用户 id={ph['id']}(单用户库升级上来的历史数据)"
              f" → {gh.get('login')}")
        conn.execute("""UPDATE users SET gh_id=?, login=?, name=?, avatar_url=?, token=?
                        WHERE id=?""",
                     (gh.get("id"), gh.get("login"), gh.get("name"),
                      gh.get("avatar_url"), gh.get("token"), ph["id"]))
        conn.commit()
        return ph["id"], False

    cur = conn.execute(
        "INSERT INTO users (gh_id, login, name, avatar_url, token) VALUES (?,?,?,?,?)",
        (gh.get("id"), gh.get("login"), gh.get("name"),
         gh.get("avatar_url"), gh.get("token")))
    conn.commit()
    return cur.lastrowid, True


def get_user(conn, user_id):
    return conn.execute(
        "SELECT id, gh_id, login, name, avatar_url FROM users WHERE id = ?",
        (user_id,)).fetchone()


def user_token(conn, user_id):
    row = conn.execute("SELECT token FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["token"] if row else None


# ---------------- 会话 ----------------

def create_session(conn, user_id):
    """发一个新会话,返回那个随机串(它会被放进 cookie)。"""
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    conn.commit()
    return token


def user_by_session(conn, token):
    """按会话串找人。找不到(或没传)返回 None。"""
    if not token:
        return None
    return conn.execute("""
        SELECT u.id, u.gh_id, u.login, u.name, u.avatar_url
        FROM sessions AS s JOIN users AS u ON u.id = s.user_id
        WHERE s.token = ?""", (token,)).fetchone()


def delete_session(conn, token):
    if token:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def count_users(conn):
    return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


# ---------------- OAuth state(防 CSRF)----------------
# 存服务端而不是 cookie —— 原因见 schema.sql 里的注释。

def save_state(conn, state):
    conn.execute("INSERT OR REPLACE INTO oauth_states (state) VALUES (?)", (state,))
    # 顺手清掉过期的(超过 30 分钟没用上的),免得这张表无限长
    conn.execute("DELETE FROM oauth_states "
                 "WHERE created_at < strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-30 minutes')")
    conn.commit()


def consume_state(conn, state):
    """这个 state 是我们发出去的吗?是就删掉(一次性)并返回 True。"""
    if not state:
        return False
    row = conn.execute("SELECT state FROM oauth_states WHERE state = ?",
                       (state,)).fetchone()
    if not row:
        return False
    conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
    conn.commit()
    return True


def _migrate_multiuser(conn):
    """把单用户的表升级成多用户:加 user_id,老数据归给"我"。

    starred / following 的**主键变了**(单列 → 复合列),SQLite 改不了主键,
    只能重建表 —— 和当初给 events 加 CHECK 是同一套做法。

    events / comments 只是加一列,用 ALTER TABLE 就行,不用重建。
    """
    # ⚠️ 这里**故意不写总闸门**(比如开头来一句"starred 有 user_id 就整体 return")。
    #
    # 起初确实有这么一个,而它是个 bug。原因:
    # starred / following / events / comments 是四次**各自独立落地**的操作
    # (executescript 会先隐式提交),不是一个原子的大事务。
    # 进程要是在"starred 升完了、following 还没升"之间被杀掉 ——
    # 崩溃、OOM、被 kill,或者两个进程同时跑 init_db
    # (注意 init_db 不只在启动时跑:/auth/login、/auth/callback、全站搜索都会调它,
    #  而 run_daily.sh 的 flock 只锁得住采集脚本、锁不住 server)——
    # 下次启动时 starred 已经有 user_id,总闸门就会直接放行过去,
    # **following 永远升不了**。
    #
    # 那之后 list_following / add_event / recent_events 全报
    # "no such column: user_id",一路 500,而且**再也不会自愈** ——
    # 因为让它们坏掉的那个判断,同时也阻止了修复。
    #
    # 改成每张表自己判断"我要不要升"。这样中断的后果只是
    # "这次少升一张,下次启动接着升",是可恢复的。
    s_cols = _table_columns(conn, "starred")
    f_cols = _table_columns(conn, "following")
    e_cols = _table_columns(conn, "events")
    c_cols = _table_columns(conn, "comments")

    need = [name for name, cols in
            (("starred", s_cols), ("following", f_cols),
             ("events", e_cols), ("comments", c_cols))
            if cols and "user_id" not in cols]
    if not need:
        return                     # 全新的库,或者已经升过了
    print(f"[migrate] 升级到多用户结构(需要升:{', '.join(need)})…")

    # 只有真要搬数据时才创建占位用户。
    # 放在前面无条件调的话,全新安装的库每次启动都会多出一个没人认领的 'me' 用户。
    me = ensure_local_user(conn)

    if "starred" in need:
        conn.executescript(f"""
            ALTER TABLE starred RENAME TO starred_old;
            CREATE TABLE starred (
                user_id     INTEGER NOT NULL,
                repo_id     INTEGER NOT NULL,
                starred_at  TEXT,
                first_seen  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                PRIMARY KEY (user_id, repo_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (repo_id) REFERENCES repos(id)
            );
            INSERT INTO starred (user_id, repo_id, starred_at, first_seen)
                SELECT {me}, repo_id, starred_at, first_seen FROM starred_old;
            DROP TABLE starred_old;
        """)

    if "following" in need:
        conn.executescript(f"""
            ALTER TABLE following RENAME TO following_old;
            CREATE TABLE following (
                user_id     INTEGER NOT NULL,
                login       TEXT    NOT NULL,
                name        TEXT,
                avatar_url  TEXT,
                html_url    TEXT,
                first_seen  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                PRIMARY KEY (user_id, login),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            INSERT INTO following (user_id, login, name, avatar_url, html_url, first_seen)
                SELECT {me}, login, name, avatar_url, html_url, first_seen
                FROM following_old;
            DROP TABLE following_old;
        """)

    for tbl in ("events", "comments"):
        if tbl in need:
            # ADD COLUMN 加不了 NOT NULL(已有行没值),所以先加可空列再回填
            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN user_id INTEGER")
            conn.execute(f"UPDATE {tbl} SET user_id = ? WHERE user_id IS NULL", (me,))

    conn.commit()
    print(f"[migrate] 完成,老数据都归给了 user_id={me}")


# (这里原来有个 _migrate_comments_add_author,给 comments 补一个 author 列。
#  它已经删掉了:那一列是在"单用户"时代加的,本意是"以后多人评论时放名字"。
#  后来真做多用户时用的是 user_id(评论作者从 users 表关联出来),
#  author 就再也没被任何代码读过 —— 线上 0 行有值。
#
#  更要紧的是它让 schema.sql 说了假话:schema.sql 描述"全新的库该长什么样",
#  但每次建新库都会被这个迁移多加一列,于是文件描述的结构和真实结构对不上。
#  留着它只会让下一个读 schema.sql 的人继续困惑。
#
#  已有的库里那一列会留着 —— 一个没人读的空列,无害,不值得为它重建表。)


def init_db(conn):
    """建表(已经建过就什么都不做 —— schema.sql 里全是 IF NOT EXISTS)。"""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    _migrate_events(conn)
    _migrate_multiuser(conn)     # 放最后:它给 events/comments 加 user_id,别被前面的重建覆盖掉


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

# starred 是"状态表":一个人对一个 repo 一行。重复同步 = 覆盖时间,不会长出第二行。
STARRED_SQL = """
INSERT INTO starred (user_id, repo_id, starred_at)
VALUES (?, ?, ?)
ON CONFLICT(user_id, repo_id) DO UPDATE SET
    starred_at = excluded.starred_at
"""

# events 是"流水表":只追加,永远不更新、不覆盖
EVENT_SQL = "INSERT INTO events (user_id, repo_id, action) VALUES (?, ?, ?)"
# neutral = 取消表态:不是"不喜欢",而是"把之前的标记撤回"
EVENT_ACTIONS = ("interested", "not_interested", "neutral")


def save_starred(conn, user_id, items):
    """items = /user/starred 的返回:[{"starred_at": ..., "repo": {...}}, ...]。

    返回写入行数。starred_at 可能是 None(没带 star+json 头),照存不误。
    """
    rows = []
    for it in items:
        repo = it.get("repo") or {}
        if repo.get("id"):
            rows.append((user_id, repo["id"], to_utc_iso(it.get("starred_at"))))
    before = conn.total_changes
    conn.executemany(STARRED_SQL, rows)
    conn.commit()
    return conn.total_changes - before


def count_starred(conn, user_id=None):
    if user_id is None:
        return conn.execute("SELECT COUNT(*) FROM starred").fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM starred WHERE user_id = ?",
                        (user_id,)).fetchone()[0]


def recent_starred(conn, user_id, limit=10):
    """按 star 时间倒序 —— 这就是"我记得我 star 过什么"的查询。"""
    return conn.execute("""
        SELECT r.full_name, r.language, r.stargazers_count, s.starred_at
        FROM starred AS s
        JOIN repos   AS r ON r.id = s.repo_id
        WHERE s.user_id = ?
        ORDER BY s.starred_at DESC
        LIMIT ?""", (user_id, limit)).fetchall()


def add_event(conn, user_id, repo_id, action):
    """记一条反馈。action 只能是 interested / not_interested / neutral。"""
    if action not in EVENT_ACTIONS:
        raise ValueError(f"action 只能是 {EVENT_ACTIONS},收到 {action!r}")
    conn.execute(EVENT_SQL, (user_id, repo_id, action))
    conn.commit()


def count_events(conn):
    return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]


def recent_events(conn, user_id, limit=10):
    """某个人的反馈流水,最近的在前。

    ⚠️ user_id 是必须的,别把它省掉。
    这个函数原来没有这个参数,调用它的 /api/events 端点也没有 require_user ——
    多用户上线之后,那就是"任何人不用登录都能读到所有人的点赞记录"。
    自己一个人用的时候完全看不出来,人一多就是隐私问题。
    """
    return conn.execute("""
        SELECT e.id, e.action, e.created_at, r.full_name
        FROM events AS e
        LEFT JOIN repos AS r ON r.id = e.repo_id
        WHERE e.user_id = ?
        ORDER BY e.id DESC
        LIMIT ?""", (user_id, limit)).fetchall()


# "当前态度" = 这个人对每个 repo 的最后一条事件。
# 事件表是流水(只追加、不改不删),所以"改主意"就再写一条 —— 历史留全,
# 而"现在到底是什么态度"用 id 最大的那条回答。
# 注意子查询里也要带 user_id —— 只按 repo_id 取最大 id 的话,
# 会拿到"别人"的表态。
_LATEST_OPINION_SQL = """
SELECT e.repo_id, e.action
FROM events AS e
WHERE e.user_id = ?
  AND e.id = (SELECT MAX(id) FROM events
              WHERE repo_id = e.repo_id AND user_id = e.user_id)
"""


def latest_opinions(conn, user_id):
    """{repo_id: action} —— 这个人对每个 repo 当前的最终态度。"""
    return {row["repo_id"]: row["action"]
            for row in conn.execute(_LATEST_OPINION_SQL, (user_id,))}


def opinion_map(conn, user_id):
    """{full_name: action} —— 给前端标按钮状态用。"""
    return {row["full_name"]: row["action"] for row in conn.execute("""
        SELECT r.full_name, e.action
        FROM events AS e JOIN repos AS r ON r.id = e.repo_id
        WHERE e.user_id = ?
          AND e.id = (SELECT MAX(id) FROM events
                      WHERE repo_id = e.repo_id AND user_id = e.user_id)""",
        (user_id,))}


# ---------------- P5:给 API 用的查询 ----------------

# 对外返回的列。集中写一处,免得每个接口各写一份列名(改字段时只改这里)
API_COLS = ("id, full_name, description, language, topics, "
            "stargazers_count, pushed_at, html_url")


def list_by_stars(conn, lang=None, limit=30):
    """按 star 数排行的候选池(保留这个函数,内部走通用查询)。"""
    return list_repos(conn, sort="stars", lang=lang, limit=limit)


# 排序方式 → 对应的 SQL 片段。集中写一处,加新排序只改这里。
SORTS = {
    "stars":  "stargazers_count DESC",
    "pushed": "pushed_at DESC",
    "name":   "full_name ASC",
}
DEFAULT_SORT = "stars"


def list_repos(conn, sort=DEFAULT_SORT, lang=None, tags=None, limit=30):
    """通用列表查询:排序 + 按语言筛 + 按标签筛(可多选)。

    标签 = GitHub 的 topics。它在库里是 JSON 字符串数组,
    所以用 SQLite 的 json_each 把它展开成行来比对。
    不能用 LIKE '%"go"%':那样 'django' 会被 "go" 误伤。

    多个标签之间是「与」:每多选一个就收窄一次范围。
    想找"又是 rust 又是 cli 的 repo",就得这样叠。
    """
    order = SORTS.get(sort, SORTS[DEFAULT_SORT])

    where, params = [], []
    if lang:
        where.append("language = ?")
        params.append(lang)

    for tag in (tags or []):
        # 标签有两个来源:作者设的 topics、我们自动补的 auto_tags。
        # 筛选要把两边都算上,否则自动补的标签点进去会是空的。
        where.append("(EXISTS (SELECT 1 FROM json_each(repos.topics) "
                     "WHERE json_each.value = ?) "
                     "OR EXISTS (SELECT 1 FROM auto_tags "
                     "WHERE auto_tags.repo_id = repos.id AND auto_tags.tag = ?))")
        params.extend([tag, tag])

    sql = f"SELECT {API_COLS} FROM repos"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order} LIMIT ?"
    params.append(limit)

    return conn.execute(sql, tuple(params)).fetchall()


def rows_by_full_names(conn, names):
    """按 full_name 批量取行 —— 全站搜索把结果写库后,用这个按原顺序取回来。"""
    names = [n for n in names if n]
    if not names:
        return []
    marks = ",".join("?" * len(names))
    return conn.execute(
        f"SELECT {API_COLS} FROM repos WHERE full_name IN ({marks})",
        tuple(names)).fetchall()


def search_repos(conn, q, limit=60):
    """按关键词搜 repo:名字、描述、标签、README、自动标签都翻一遍。

    排序按"命中在哪儿"分级:名字 > 描述 > 标签 > README。
    不做分级的话,一个在 README 里顺带提了一句的 repo 会和名字直接命中的
    排在一起,最相关的那几个反而要翻半天。
    """
    like = f"%{q}%"
    return conn.execute(f"""
        SELECT {API_COLS},
               CASE WHEN full_name  LIKE :q THEN 0
                    WHEN description LIKE :q THEN 1
                    WHEN topics      LIKE :q THEN 2
                    ELSE 3 END AS rank
        FROM repos
        WHERE full_name LIKE :q OR description LIKE :q OR topics LIKE :q
           OR id IN (SELECT repo_id FROM readmes   WHERE content LIKE :q)
           OR id IN (SELECT repo_id FROM auto_tags WHERE tag     LIKE :q)
        ORDER BY rank ASC, stargazers_count DESC
        LIMIT :lim""", {"q": like, "lim": limit}).fetchall()


def list_tags(conn, limit=300):
    """所有标签 + 各自带多少个 repo,按数量从多到少。

    两个来源合并:作者设的 topics,和我们自动补的 auto_tags。
    """
    return conn.execute("""
        SELECT tag, COUNT(*) AS n FROM (
            SELECT j.value AS tag
            FROM repos, json_each(repos.topics) AS j
            WHERE j.value IS NOT NULL AND j.value != ''
            UNION ALL
            SELECT tag FROM auto_tags WHERE tag IS NOT NULL AND tag != ''
        )
        GROUP BY tag
        ORDER BY n DESC, tag ASC
        LIMIT ?""", (limit,)).fetchall()


def tag_cloud_count(conn):
    """有标签的 repo 有多少个(两个来源任一有就算) —— 用来看覆盖率。"""
    return conn.execute("""
        SELECT COUNT(*) AS n FROM repos
        WHERE (topics IS NOT NULL AND topics NOT IN ('[]', ''))
           OR EXISTS (SELECT 1 FROM auto_tags WHERE auto_tags.repo_id = repos.id)
    """).fetchone()["n"]


# ---------------- 自动补的标签 ----------------

AUTO_TAG_SQL = "INSERT OR IGNORE INTO auto_tags (repo_id, tag) VALUES (?, ?)"


def save_auto_tags(conn, repo_id, tags):
    conn.executemany(AUTO_TAG_SQL, [(repo_id, t) for t in tags if t])
    conn.commit()


def clear_auto_tags(conn):
    conn.execute("DELETE FROM auto_tags")
    conn.commit()


def auto_tags_for(conn, repo_ids):
    """{repo_id: [标签, ...]} —— 出接口时把它们并进 topics 给前端。"""
    if not repo_ids:
        return {}
    marks = ",".join("?" * len(repo_ids))
    out = {}
    for row in conn.execute(
            f"SELECT repo_id, tag FROM auto_tags WHERE repo_id IN ({marks}) "
            "ORDER BY tag", tuple(repo_ids)):
        out.setdefault(row["repo_id"], []).append(row["tag"])
    return out


def count_auto_tags(conn):
    return conn.execute("SELECT COUNT(*) AS n FROM auto_tags").fetchone()["n"]


# ---------------- 详情页的笔记 ----------------

def add_comment(conn, user_id, repo_id, body):
    conn.execute("INSERT INTO comments (user_id, repo_id, body) VALUES (?, ?, ?)",
                 (user_id, repo_id, body))
    conn.commit()


def list_comments(conn, repo_id, limit=200):
    """某个 repo 的评论,新的在前。**带上评论者是谁** —— 这正是作者字段(users)的用处。"""
    return conn.execute("""
        SELECT c.id, c.body, c.created_at,
               u.login AS author_login, u.name AS author_name, u.avatar_url
        FROM comments AS c LEFT JOIN users AS u ON u.id = c.user_id
        WHERE c.repo_id = ?
        ORDER BY c.id DESC LIMIT ?""", (repo_id, limit)).fetchall()


def count_comments(conn):
    return conn.execute("SELECT COUNT(*) AS n FROM comments").fetchone()["n"]


# ---------------- 关注的开发者 ----------------

FOLLOWING_SQL = """
INSERT INTO following (user_id, login, name, avatar_url, html_url)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(user_id, login) DO UPDATE SET
    name       = excluded.name,
    avatar_url = excluded.avatar_url,
    html_url   = excluded.html_url
"""


def save_following(conn, user_id, users):
    """users = GitHub /user/following 的返回。返回写入行数。"""
    rows = [(user_id, u.get("login"), u.get("name"), u.get("avatar_url"), u.get("html_url"))
            for u in users if u.get("login")]
    before = conn.total_changes
    conn.executemany(FOLLOWING_SQL, rows)
    conn.commit()
    return conn.total_changes - before


# 关注列表的排序方式。注意 "关注时间" 用的是 first_seen ——
# GitHub 的接口**不返回真实的关注时间**,所以只能用它当近似:
# 它记录的是"我们第一次同步到这个人"的时刻,所以对开始同步之后才关注的人才有意义。
FOLLOWING_SORTS = {
    "recent": "first_seen DESC, login COLLATE NOCASE",
    "oldest": "first_seen ASC, login COLLATE NOCASE",
    "name":   "login COLLATE NOCASE ASC",
}


def list_following(conn, user_id, limit=500, sort="name", q=None):
    """这个人关注的人。支持按名字/关注时间排序,以及按关键词过滤。"""
    order = FOLLOWING_SORTS.get(sort, FOLLOWING_SORTS["name"])

    where, params = "WHERE user_id = ?", [user_id]
    if q:
        like = f"%{q}%"
        where += " AND (login LIKE ? OR IFNULL(name, '') LIKE ?)"
        params += [like, like]

    sql = (f"SELECT login, name, avatar_url, html_url, first_seen FROM following "
           f"{where} ORDER BY {order} LIMIT ?")
    params.append(limit)
    return conn.execute(sql, tuple(params)).fetchall()


def count_following(conn, user_id=None):
    if user_id is None:
        return conn.execute("SELECT COUNT(*) AS n FROM following").fetchone()["n"]
    return conn.execute("SELECT COUNT(*) AS n FROM following WHERE user_id = ?",
                        (user_id,)).fetchone()["n"]


def comment_counts(conn, repo_ids):
    """{repo_id: 条数} —— 列表里每条都要显示评论数,一次查完。

    别在循环里一条条查:那样 30 条就是 30 次查询。
    """
    repo_ids = [r for r in repo_ids if r]
    if not repo_ids:
        return {}
    marks = ",".join("?" * len(repo_ids))
    return {row["repo_id"]: row["n"] for row in conn.execute(
        f"SELECT repo_id, COUNT(*) AS n FROM comments "
        f"WHERE repo_id IN ({marks}) GROUP BY repo_id", tuple(repo_ids))}


def repos_without_topics(conn):
    """作者没设 topics 的 repo(自动补标签就补这些)。"""
    return conn.execute(
        f"SELECT {API_COLS} FROM repos "
        "WHERE topics IS NULL OR topics IN ('[]', '')").fetchall()


GROWTH_SQL = """
SELECT r.id,
       r.full_name,
       r.description,
       r.language,
       r.html_url,
       r.topics,
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


def starred_list(conn, user_id, limit=200):
    """某个用户 star 过的仓库,按 star 时间倒序。

    ⚠️ topics 必须带上。少了它,接口出口的 attach_tags 拿到的就是 None,
    只并得进 auto_tags,而**作者自己设的 topics 全丢** ——
    表现是"已收藏"页的卡片标签是空的/只剩自动标签,
    但同一个仓库在 Trending 页却标签齐全。
    又是"同一个字段两处口径不一致"(这类问题在这个项目里出现过好几次了)。
    """
    return conn.execute("""
        SELECT r.id, r.full_name, r.description, r.language, r.html_url,
               r.stargazers_count, r.topics, s.starred_at
        FROM starred AS s JOIN repos AS r ON r.id = s.repo_id
        WHERE s.user_id = ?
        ORDER BY s.starred_at DESC LIMIT ?""", (user_id, limit)).fetchall()


def starred_repo_ids(conn, user_id):
    """这个人 star 过的所有 repo id —— 推荐要用它当口味信号。"""
    return {r["repo_id"] for r in conn.execute(
        "SELECT repo_id FROM starred WHERE user_id = ?", (user_id,))}


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


def has_readme_row(conn, repo_id):
    """有没有"抓过"的记录。

    注意和"内容为空"的区别:抓过但那个 repo 没有 README,存的是一条空字符串 ——
    那说明我们查过了,不该再查第二遍。没有行才是"还没查过"。
    """
    return conn.execute("SELECT 1 FROM readmes WHERE repo_id = ?",
                        (repo_id,)).fetchone() is not None


def repo_delta(conn, repo_id):
    """最近两个快照日之间这个 repo 的 star 增量;快照不足两份就返回 None。"""
    rows = conn.execute("""
        SELECT stargazers_count FROM repo_snapshots
        WHERE repo_id = ? ORDER BY snapshot_date DESC LIMIT 2""", (repo_id,)).fetchall()
    if len(rows) < 2:
        return None
    return rows[0]["stargazers_count"] - rows[1]["stargazers_count"]


def starred_at_of(conn, user_id, repo_id):
    """这个人什么时候 star 的它;没 star 过返回 None。"""
    row = conn.execute("SELECT starred_at FROM starred WHERE user_id = ? AND repo_id = ?",
                       (user_id, repo_id)).fetchone()
    return row["starred_at"] if row else None


if __name__ == "__main__":
    c = get_conn()
    init_db(c)
    print(f"数据库:{DB_PATH}")
    print(f"repos 表现有 {count_repos(c)} 行")
    print(f"repo_snapshots 表现有 {count_snapshots(c)} 行")
    print(f"starred        表现有 {count_starred(c)} 行")
    print(f"events         表现有 {count_events(c)} 行")
