#!/usr/bin/env python3
"""P2:把 P1 拉下来的 data/raw/*.json 灌进 SQLite。

用法:
    python load_raw.py

幂等:重复跑多少次,repos 行数都不变(靠 ON CONFLICT(full_name) 做 upsert)。
"""
import glob
import json
import os

from db import count_repos, get_conn, init_db, upsert_repos

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")


def main():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "*.json")))
    if not files:
        print("data/raw/ 里没有 JSON,先跑 fetch_repos.py")
        return

    conn = get_conn()
    init_db(conn)
    before = count_repos(conn)

    total_read = 0
    for path in files:
        with open(path, encoding="utf-8") as f:
            repos = json.load(f)
        written, _ = upsert_repos(conn, repos)
        total_read += len(repos)
        print(f"  {os.path.basename(path):>18}  读 {len(repos):>4} 条 → 落库 {written:>4} 行")

    after = count_repos(conn)
    print(f"\n文件 {len(files)} 个,原始记录 {total_read} 条")
    print(f"repos 表:{before} 行 → {after} 行(本次新增 {after - before} 行)")
    if after - before < total_read:
        print("(原始记录 > 新增行数,说明有重复的 full_name —— 被 UNIQUE 挡住了,这是对的)")


if __name__ == "__main__":
    main()
