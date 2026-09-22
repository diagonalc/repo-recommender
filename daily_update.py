#!/usr/bin/env python3
"""P3:每日增量更新 —— 刷新 repo 元数据 + 记一份当天的 star 快照。

用法:
    python3 daily_update.py

每天跑一次,做三件事:
    1. 重跑 P1 那 12 个 search 查询,拿到"现在"的 repo 数据(只要 12 次请求,
       不用给 1000 多个 repo 逐个调详情接口那种上千次的笨办法)
    2. upsert 进 repos 表 —— 元数据刷新(star 数、pushed_at 等跟着更新)
    3. 把每个 repo 今天的 star 数写进 repo_snapshots

副作用:data/raw/*.json 会被覆盖成"最新一批原始数据"。

为什么用 search 重拉而不是逐个 repo 查详情:
    详情接口 /repos/{owner}/{repo} 要按 repo 数调用(1200 次!),而 search 接口
    一次给 100 个。用量差 100 倍 —— 这就是"选对接口"的价值。
    代价:search 返回的是当前榜单,冷门 repo 可能掉出前 100 就不再被刷新。
"""
import time

from db import (count_repos, count_snapshots, get_conn, init_db,
                save_snapshots, today_utc, upsert_repos)
# 复用 P1 的取数逻辑:别复制粘贴,直接 import 那几个函数
from fetch_repos import (LANGUAGES, PAGES_PER_LANG, REQUEST_GAP, fetch_page,
                         save_page)


def collect_repos():
    """按语言/页拉一遍,返回按 full_name 去重后的 repo 列表。

    某一个语言失败(比如撞限流)不中断整轮 —— 记下来,继续下一个语言。
    定时任务的原则:能拿到多少算多少,别让一个环节崩掉整个 job
    (崩掉的后果是"这一天没有任何快照",比"少一个语言"严重得多)。
    """
    seen = {}
    failed = []
    for lang in LANGUAGES:
        try:
            for page in range(1, PAGES_PER_LANG + 1):
                repos = fetch_page(lang, page)
                if not repos:
                    print(f"  {lang} 没有更多了")
                    break
                save_page(lang, page, repos)    # 顺便刷新 data/raw
                for r in repos:
                    if r.get("full_name"):
                        # 同一 repo 可能出现在多页(榜单在动),用 full_name 去重
                        seen[r["full_name"]] = r
                time.sleep(REQUEST_GAP)
        except RuntimeError as e:
            print(f"  [!] {lang} 拉取失败,跳过:{e}")
            failed.append(lang)

    if failed:
        print(f"注意:这些语言没拉到 → {', '.join(failed)}(今天的快照会缺这部分)")
    return list(seen.values())


def main():
    day = today_utc()
    print(f"=== daily_update:{day}(UTC)===")

    repos = collect_repos()
    print(f"拉到 {len(repos)} 个 repo(已去重)")

    conn = get_conn()
    init_db(conn)

    upsert_repos(conn, repos)                   # 1. 刷新元数据
    written = save_snapshots(conn, repos, day)  # 2. 记今天这份快照

    print(f"\nrepos 表:{count_repos(conn)} 行")
    print(f"快照:本次写入 {written} 行(日期 {day}),库里快照共 {count_snapshots(conn)} 行")
    if count_snapshots(conn) == written:
        print("(这是第一份快照 —— 明天再跑一次,trending.py 才有的可比)")


if __name__ == "__main__":
    main()
