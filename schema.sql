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
