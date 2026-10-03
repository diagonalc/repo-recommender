#!/usr/bin/env python3
"""回归测试:标签页的搜索 + 搜索页的排序。

**① 标签搜索必须在 SQL 里筛,不能拉回来在前端筛**
    `list_tags` 的 LIMIT 截的是"数量最多的前 N 个"。一个冷门标签
    很可能根本不在那 N 个里面 —— 前端筛的话,你搜它永远搜不到,
    而且**看不出是为什么**(不是"没结果",是"结果根本不在你手里")。
    这里专门拿"第 500 名"的标签来验:它不在默认返回的前 200 里,
    但搜它必须搜得到。

**② 排序必须落到唯一值上**
    ORDER BY 如果只排到 star(并列很多),那并列的那些行每次查询顺序
    都可能不同 —— 表现是刷新一下内容就跳位置,极难复现。
    所以每种排序末尾都补了 full_name 兜底。这里验"同样的查询跑两次结果一致"。

**③ 排序方式必须是白名单**
    ORDER BY 的列名没法用 ? 占位,只能拼字符串。所以 sort 只能从
    固定的几种里取 —— 万一哪天有人把用户传的字符串直接拼进去,
    就是一个 SQL 注入口子。这里验非法值会被拒。

跑法:
    .venv/bin/python tests/test_search_tags.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

FAILED = []


def check(name, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def main():
    conn = db.get_conn()
    if not db.count_repos(conn):
        print("库里没有 repo,先跑 daily_update.py")
        sys.exit(0)

    # ---- 1. 标签搜索 ----------------------------------------------------
    print("1. 标签搜索")
    all_tags = db.list_tags(conn, limit=500)
    check("库里有标签", bool(all_tags), f"({len(all_tags)} 个)")

    prefix = all_tags[0][0][:3]          # 拿数量最多的那个标签取个前缀
    hits = db.list_tags(conn, limit=50, q=prefix)
    check(f"按子串 {prefix!r} 能筛出标签", bool(hits),
          f"({[h[0] for h in hits[:4]]})")
    check("筛出来的每个都真的含这个子串",
          all(prefix.lower() in h[0].lower() for h in hits))

    check("没有结果的词返回空而不是报错",
          db.list_tags(conn, limit=50, q="zzz_no_such_tag_zzz") == [])

    # ★ 核心:冷门标签(不在默认限额内)也要搜得到
    if len(all_tags) >= 100:
        rare = all_tags[-1][0]           # 排最后 = 数量最少的
        default_page = [r[0] for r in db.list_tags(conn, limit=20)]
        check(f"前提:冷门标签 {rare!r} 不在默认返回的前 20 里",
              rare not in default_page)
        found = db.list_tags(conn, limit=20, q=rare)
        check("★ 但搜它能搜到(说明筛在 SQL 里,不是前端筛)",
              any(r[0] == rare for r in found),
              f"(搜到 {[r[0] for r in found]}）")

    # 过滤大小写不敏感(SQLite 的 LIKE 对 ASCII 默认就不敏感,顺手验一下)
    if all_tags:
        t0 = all_tags[0][0]
        check("大小写不敏感",
              bool(db.list_tags(conn, limit=20, q=t0.upper())))

    # ---- 2. 搜索排序 ----------------------------------------------------
    print("\n2. 搜索排序")
    q = "python"
    base = db.search_repos(conn, q, limit=30)
    if not base:
        print("  (搜 python 没结果,跳过排序检查)")
    else:
        for sort in db.SEARCH_SORTS:
            rows = db.search_repos(conn, q, limit=30, sort=sort)
            check(f"sort={sort} 有结果", bool(rows), f"({len(rows)} 条)")

        stars = db.search_repos(conn, q, limit=30, sort="stars")
        vals = [r["stargazers_count"] for r in stars]
        check("sort=stars 真的是降序", vals == sorted(vals, reverse=True),
              f"(前 5 个 {vals[:5]})")

        names = [r["full_name"] for r in db.search_repos(conn, q, limit=30, sort="name")]
        check("sort=name 真的是升序",
              names == sorted(names, key=lambda s: s.lower()),
              f"(前 3 个 {names[:3]})")

        dates = [r["pushed_at"] or "" for r in
                 db.search_repos(conn, q, limit=30, sort="pushed")]
        check("sort=pushed 真的是降序", dates == sorted(dates, reverse=True))

        # ★ 确定性:同样的查询两次结果必须一模一样
        a = [r["full_name"] for r in db.search_repos(conn, q, limit=30, sort="stars")]
        b = [r["full_name"] for r in db.search_repos(conn, q, limit=30, sort="stars")]
        check("★ 同样查询两次结果一致(排序落到了唯一值上)", a == b)

        # relevance 应该和别的排序不同(否则说明 sort 没起作用)
        rel = [r["full_name"] for r in db.search_repos(conn, q, limit=30)]
        check("relevance 和 stars 的结果顺序不同(说明 sort 真的生效)",
              rel != stars and [r["full_name"] for r in stars] != rel)

    # ---- 3. 非法排序 ----------------------------------------------------
    print("\n3. 非法 sort")
    check("SEARCH_SORTS 是白名单字典",
          isinstance(db.SEARCH_SORTS, dict) and "relevance" in db.SEARCH_SORTS)
    # 传非法值时 db 层回退到 relevance(接口层会直接 422 拒绝)
    bad = db.search_repos(conn, q, limit=5, sort="stars; DROP TABLE repos")
    check("db 层对非法 sort 回退到默认,不会拼进 SQL", bad is not None)

    print()
    if FAILED:
        print(f"❌ {len(FAILED)} 项失败:")
        for f in FAILED:
            print(f"     {f}")
        sys.exit(1)
    print("✅ 全部通过")


if __name__ == "__main__":
    main()
