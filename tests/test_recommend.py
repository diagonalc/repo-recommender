#!/usr/bin/env python3
"""回归测试:推荐的两件事 —— 探索位、star 与 like 的权重差。

**① 分页稳定性(最容易写错的一条)**
    推荐靠 offset 分页(滚到底自动加载下一批)。加了探索位之后,
    "每 10 个插 1 个"必须插在**固定位置**上 ——
    如果每次算出来的顺序不一样:

        [第 1 批]                    [第 2 批]
        1..20                        21..40
        其中第 10 位是探索位 A        如果这次第 10 位的探索位变成了 B,
                                     那么 A 就被跳过、B 出现两次

    用户看到的是"这个怎么又出现一次""刚看过的怎么没了",
    而且完全看不出是哪里错了。所以这里要验的是:
    **一次要 100 条 == 分两次各要 50 条拼起来**,必须一字不差。

**② 探索位真的"不像"**
    它存在的意义是打破信息茧房。如果挑出来的仓库相似度并不低,
    那就是在骗自己 —— 白占一个位置,还标着"换换口味"。

**③ star 的权重确实比 like 高**
    改这个权重必须**真的影响结果**。这里容易犯的错是"先取 max 再乘权重" ——
    最大值乘一个常数还是最大值,排序完全不变,等于没改。

跑法(需要向量缓存和至少一个有点口味的用户):
    .venv/bin/python tests/test_recommend.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
import recommend

FAILED = []


def check(name, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def skip(msg):
    print(f"\n⏭️  {msg}")
    sys.exit(0)


def pick_user(conn):
    """找一个有 star、也有"感兴趣"的用户 —— 两种信号都有才测得出权重差。"""
    row = conn.execute("""
        SELECT u.id, u.login,
               (SELECT COUNT(*) FROM starred s WHERE s.user_id = u.id) AS n_star,
               (SELECT COUNT(*) FROM events e WHERE e.user_id = u.id
                  AND e.action = 'interested') AS n_like
        FROM users u
        ORDER BY u.id""").fetchall()
    for r in row:
        if r["n_star"] >= 2 and r["n_like"] >= 1:
            return r["id"], r["login"], r["n_star"], r["n_like"]
    return None


def main():
    conn = db.get_conn()
    who = pick_user(conn)
    if not who:
        skip("没有同时有 star 和'感兴趣'的用户,测不了权重差")
    uid, login, n_star, n_like = who
    print(f"用 {login}({n_star} 个 star、{n_like} 个感兴趣)\n")

    try:
        full = recommend.recommend_for(conn, uid, n=100, offset=0)
    except RuntimeError as e:
        skip(f"算不出推荐:{e}")

    if len(full) < 100:
        skip(f"只有 {len(full)} 条推荐,不够验分页")

    # ---- 1. ★ 分页稳定性 ------------------------------------------------
    print("1. 分页稳定性(一次要 100 == 分两次各要 50)")
    p1 = recommend.recommend_for(conn, uid, n=50, offset=0)
    p2 = recommend.recommend_for(conn, uid, n=50, offset=50)
    joined = [x["full_name"] for x in p1] + [x["full_name"] for x in p2]
    whole = [x["full_name"] for x in full]
    check("拼接结果和一次要到的完全一致", joined == whole,
          "" if joined == whole else
          f"(第 {next(i for i, (a, b) in enumerate(zip(joined, whole)) if a != b) + 1} 条开始不一致)")

    names = [x["full_name"] for x in full]
    check("整份列表没有重复项", len(names) == len(set(names)),
          f"({len(names)} 条里有 {len(names) - len(set(names))} 个重复)")

    check("两次调用结果相同(确定性)",
          [x["full_name"] for x in recommend.recommend_for(conn, uid, n=100, offset=0)]
          == whole)

    # ---- 2. 探索位 ------------------------------------------------------
    print("\n2. 探索位")
    explores = [i for i, x in enumerate(full) if x["because_kind"] == "explore"]
    check("确实有探索位", bool(explores), f"({len(explores)} 个 / 100 条)")
    # 每 10 个位置插一个 → 在 100 条里大约 10 个
    check("比例接近 1/10", 5 <= len(explores) <= 15, f"({len(explores)} 个)")
    check("插在固定位置上(第 10、20、30…条)",
          all((i + 1) % recommend.EXPLORE_EVERY == 0 for i in explores),
          f"(实际位置 {[i + 1 for i in explores][:6]}…)")

    opinions = db.latest_opinions(conn, uid)
    has_star = [x["full_name"] for x in full
                if x["because_kind"] == "explore" and x.get("because_of")]
    check("探索位不带'因为你…'的理由(它不像你,不该硬编一个)",
          not has_star, ", ".join(has_star[:3]))
    check("探索位不带 similarity 字段(不假装它像你)",
          all("similarity" not in x for x in full if x["because_kind"] == "explore"))
    check("探索位有 delta 或明确为 None(前端要显示涨了多少)",
          all("delta" in x for x in full if x["because_kind"] == "explore"))

    # 用原始余弦验一下"探索位确实不像"
    print("\n3. 探索位挑出来的确实不像(用原始余弦复核)")
    import numpy as np
    from features import load_features
    matrix, ids = load_features()
    pos = {rid: i for i, rid in enumerate(ids)}
    starred_ids = db.starred_repo_ids(conn, uid)
    like_ids = {r for r, a in opinions.items() if a == "interested"}
    my_pos = [pos[r] for r in (starred_ids | like_ids) if r in pos]
    if my_pos:
        sims = np.asarray((matrix[my_pos] @ matrix.T).todense()).max(axis=0)
        name_to_i = {meta_id: i for i, meta_id in enumerate(ids)}
        fname_of = {r["id"]: r["full_name"] for r in
                    conn.execute("SELECT id, full_name FROM repos")}
        idx_of_name = {v: k for k, v in fname_of.items()}
        worst = 0.0
        for x in full:
            if x["because_kind"] != "explore":
                continue
            rid = idx_of_name.get(x["full_name"])
            if rid in name_to_i:
                worst = max(worst, float(sims[name_to_i[rid]]))
        check(f"每个探索位的相似度都 < {recommend.EXPLORE_MAX_SIM}", worst < recommend.EXPLORE_MAX_SIM,
              f"(最大的一个是 {worst:.3f})")

    # ---- 4. star 权重要真的起作用 ---------------------------------------
    print("\n4. star 的权重确实比 like 高")
    saved = recommend.LIKE_WEIGHT
    try:
        recommend.LIKE_WEIGHT = recommend.STAR_WEIGHT     # 拉平:两种信号一样重
        flat = recommend.recommend_for(conn, uid, n=100, offset=0)
    finally:
        recommend.LIKE_WEIGHT = saved

    a = [(x["full_name"], x.get("score")) for x in full]
    b = [(x["full_name"], x.get("score")) for x in flat]
    check("改权重会改变结果(说明加权发生在取最大值**之前**)", a != b)

    # 说明:如果实现成"先 max 再乘权重",a 和 b 会完全一样 —— 那是白改。
    if a == b:
        print("      ↑ 说明加权没生效。检查是不是写成了 max(sim) * w 而不是 max(sim * w)")

    print()
    if FAILED:
        print(f"❌ {len(FAILED)} 项失败:")
        for f in FAILED:
            print(f"     {f}")
        sys.exit(1)
    print("✅ 全部通过")


if __name__ == "__main__":
    main()
