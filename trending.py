#!/usr/bin/env python3
"""P3:增速榜 —— 最近两个快照日之间,star 涨得最快的 Top N。

用法:
    python3 trending.py          # 默认 Top 30
    python3 trending.py 10       # Top 10

思路:
    增速 = 今天这份快照 - 上一次那份快照(同一个 repo 的两行相减)。
    所以 SQL 里把 repo_snapshots 和自己 join:一别名 cur(今天)、一别名 prev(上次)。
    这也是为什么 P2 要给 full_name 做 UNIQUE、行身份保持稳定 —— 快照才能挂上去。
"""
import heapq
import sys

from db import get_conn, snapshot_dates

TOP_N = 30

# cur = 最新那天,prev = 上一次那天。两个日期由 main() 查出来再传进去(? 占位)
SQL = """
SELECT r.full_name,
       r.language,
       r.html_url,
       cur.stargazers_count                          AS stars,
       prev.stargazers_count                         AS prev_stars,
       cur.stargazers_count - prev.stargazers_count  AS delta
FROM repo_snapshots AS cur
JOIN repo_snapshots AS prev
     ON prev.repo_id = cur.repo_id
JOIN repos AS r
     ON r.id = cur.repo_id
WHERE cur.snapshot_date  = ?
  AND prev.snapshot_date = ?
"""


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else TOP_N

    conn = get_conn()
    dates = snapshot_dates(conn)

    if len(dates) < 2:
        print(f"库里只有 {len(dates)} 个快照日期:{dates or '(空)'}")
        print("算增速至少要两份不同日期的快照 —— 明天再跑一次 daily_update.py 就有了。")
        return

    cur_day, prev_day = dates[0], dates[1]      # 最新的两天
    rows = conn.execute(SQL, (cur_day, prev_day)).fetchall()
    print(f"对比 {prev_day} → {cur_day}(共 {len(rows)} 个 repo 有可比数据)\n")

    # Top-K 用堆:heapq.nlargest 是 O(n log k),只排序"要的那几个",
    # 比 sorted(全部)[:k] 的 O(n log n) 省 —— 你 DS 学的堆,这里就是实战。
    # (数据才几千行,两种写法都够快;等 repo 到几十万,差别就出来了。
    #  真到那时更该交给 SQL:ORDER BY delta DESC LIMIT k,数据库直接算完。)
    top = heapq.nlargest(n, rows, key=lambda row: row["delta"])

    print(f"{'#':>3}  {'delta':>6}  {'stars':>8}  {'涨%':>6}   repo")
    print("-" * 72)
    for i, row in enumerate(top, 1):
        delta, prev = row["delta"], row["prev_stars"]
        # 涨幅:绝对增量会被"老 repo 基数大"碾压,所以补一个相对指标
        pct = (delta / prev * 100) if prev else 0.0
        print(f"{i:>3}  {delta:>+6}  {row['stars']:>8}  {pct:>5.1f}%   "
              f"{row['full_name']} ({row['language']})")

    print("\n提示:左列 delta 是绝对增量(老 repo 天然占优);'涨%' 是大 repo 小 repo"
          "\n      都能比的相对增速。想更公平,可以按涨%排序再看一版。")


if __name__ == "__main__":
    main()
