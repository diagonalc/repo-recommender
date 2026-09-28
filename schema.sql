-- P2 存储层:SQLite 表结构
-- 什么时候被执行:db.py 里的 init_db() 会读这个文件并整段执行
-- 想手动建表也行:sqlite3 data/repos.db < schema.sql

CREATE TABLE IF NOT EXISTS repos (
    id                INTEGER PRIMARY KEY,     -- 直接用 GitHub 的 repo id 当主键(它天然唯一)
    full_name         TEXT    NOT NULL UNIQUE, -- "owner/repo"。UNIQUE = 同一个 repo 永远只有一行
    description       TEXT,
    language          TEXT,
    topics            TEXT,                    -- SQLite 没有数组类型 → 存 JSON 字符串,如 ["cli","rust"]
    stargazers_count  INTEGER NOT NULL DEFAULT 0,
    pushed_at         TEXT,                    -- 统一用 UTC 的 ISO8601,如 2026-09-14T00:40:35Z
    html_url          TEXT,
    fetched_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);                                             -- fetched_at = 我们本地把它写进库的时间

-- 索引:让"按 star 排序""按语言筛选"不必全表扫描(数据上万后差别明显)
CREATE INDEX IF NOT EXISTS idx_repos_stars    ON repos(stargazers_count DESC);
CREATE INDEX IF NOT EXISTS idx_repos_language ON repos(language);


-- ============ P3:每日 star 快照 ============
-- repos 存的是"此刻"的 star 数(每次更新被覆盖);
-- 想算"涨了多少"就必须把历史留档 —— 这张表一个 repo 一天记一行,只增不改。
CREATE TABLE IF NOT EXISTS repo_snapshots (
    repo_id           INTEGER NOT NULL,    -- 指向 repos.id
    snapshot_date     TEXT    NOT NULL,    -- UTC 日期 'YYYY-MM-DD'(只到"天",一天一份)
    stargazers_count  INTEGER NOT NULL,
    PRIMARY KEY (repo_id, snapshot_date),  -- 同一 repo 同一天只有一行 → 当天重跑 = 覆盖,不产生重复
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);

-- 算榜时要"取最近两个日期",按日期查,给它建索引
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON repo_snapshots(snapshot_date);


-- ============ P4:你自己的行为数据 ============
-- 推荐系统的"口味信号"就来自这两张表:
--   starred = 强信号(你主动收藏)
--   events  = 弱信号/显式反馈(你点"感兴趣/不感兴趣")

CREATE TABLE IF NOT EXISTS starred (
    repo_id     INTEGER PRIMARY KEY,   -- 一个 repo 只能被 star 一次 → 它就是主键
    starred_at  TEXT,                  -- GitHub 给的真实 star 时间(UTC ISO8601)
    first_seen  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);
-- 注意 starred_at 和 first_seen 是两回事:
--   starred_at  = 你当初 star 它的时间(GitHub 记的)
--   first_seen  = 我们的脚本第一次看到它的时间(我们记的)
-- 拿 /user/starred 时带上 Accept: application/vnd.github.star+json 才有 starred_at,
-- 不带这个头 GitHub 只回 repo 元数据,时间就丢了。

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,   -- 事件流:同一个人可以对同一个 repo 反复表态
    repo_id     INTEGER NOT NULL,
    action      TEXT    NOT NULL CHECK (action IN ('interested','not_interested')),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);
-- 为什么 events 用自增 id 而不是 (repo_id, action) 做主键:
-- 行为是"流",记录的是"什么时候做了什么",同一条可以发生很多次 —— 要留全集。
-- starred 是"状态"(sta 或没 sta),所以一个 repo 只留一行。状态和流,建表方式不同。

CREATE INDEX IF NOT EXISTS idx_events_repo   ON events(repo_id);
CREATE INDEX IF NOT EXISTS idx_events_action ON events(action);
