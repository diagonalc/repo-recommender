#!/usr/bin/env python3
"""P6:我的推荐 —— 从"我 star 过的 + 我点过感兴趣的"出发,找像它们、但我还没 star 的。

用法:
    .venv/bin/python recommend.py          # Top 20
    .venv/bin/python recommend.py 10

打分公式(刻意做得简单可调):
    最终分 = 相似度 × 热度系数
    相似度   = 和我最像的那个 star 之间的余弦相似度
    热度系数 = 1 + 0.1 × log10(星数)

为什么要乘热度:
    光看相似度,会推出一堆"很像但没人用、早就停更"的 repo。
    乘一个随星数缓慢增长(取对数)的系数,让热门略占优,又不会让大 repo 通吃 ——
    取对数就是为了压住"48 万星 vs 5 百星"这种量级碾压。

为什么每条推荐都带"因为你 star 过 X":
    推荐结果不可解释就没法调。看到"为什么推它",你才能判断是相似度算歪了,
    还是你自己的口味数据太少 —— 否则只能盲调权重。
"""
import sys

import numpy as np

import db
from features import load_features

POPULARITY_WEIGHT = 0.1


def recommend_for(conn, n=20):
    """算推荐列表。命令行和 HTTP 接口共用这一份逻辑(别写两遍)。

    返回 list[dict],已按分数从高到低排好。
    没有向量缓存或没有口味信号时抛 RuntimeError,由调用方决定怎么呈现
    (命令行打印一行,HTTP 接口转成 409)。
    """
    try:
        matrix, ids = load_features()      # 没缓存时它抛 SystemExit
    except SystemExit as e:
        raise RuntimeError(str(e))

    pos = {rid: i for i, rid in enumerate(ids)}
    opinions = db.latest_opinions(conn)

    # 口味信号 = 我 star 过的 + 我点过"感兴趣"的。
    # 两者都是正向偏好,区别只在强度(star 明显比一次点击重)。
    # 这里先一视同仁 —— 因为算的是"最像的那个信号",加权意义不大;
    # 等以后改成"相似度累加"时,再给 star 更高的权重。
    starred = {r["repo_id"] for r in conn.execute("SELECT repo_id FROM starred")}
    liked = {rid for rid, act in opinions.items() if act == "interested"}
    positive = starred | liked

    # 记住每个正向信号是"star 来的"还是"点击来的" —— 推荐理由得说实话。
    # 既 star 又点过感兴趣的,按 star 算(更强的信号)。
    kind = {rid: "starred" for rid in starred}
    for rid in liked:
        kind.setdefault(rid, "interested")

    my_pos = [pos[r] for r in positive if r in pos]
    if not my_pos:
        raise RuntimeError(
            "还没有口味信号。先跑 sync_stars.py,或在页面上点几个[感兴趣]")

    # (我的 k 个正向信号) × (全部 repo) → 相似度矩阵
    sims = np.asarray((matrix[my_pos] @ matrix.T).todense())
    best_sim = sims.max(axis=0)        # 每个候选:和我最像的那个信号的相似度
    best_from = sims.argmax(axis=0)    # 是哪一个信号贡献的

    # 负向信号:当前态度是"不感兴趣"的,直接排除。
    # 关键:用 latest_opinions(每个 repo 的最新一条),不是"曾经点过" ——
    # 你改主意了,推荐就得跟着改。
    banned = {pos[rid] for rid, act in opinions.items()
              if act == "not_interested" and rid in pos}
    my_set = set(my_pos)
    meta = {row["id"]: (row["full_name"], row["language"], row["stargazers_count"],
                        row["description"], row["html_url"])
            for row in conn.execute(
                "SELECT id, full_name, language, stargazers_count, description, "
                "html_url FROM repos")}

    out = []
    for i, rid in enumerate(ids):
        if i in my_set or i in banned or best_sim[i] <= 0:
            continue
        name, lang, stars, desc, url = meta.get(rid, ("?", None, 0, None, None))
        popularity = 1 + POPULARITY_WEIGHT * np.log10(max(stars, 1))
        # best_from[i] 是"我的第几个正向信号",要转回 repo_id 再转成名字
        src_id = ids[my_pos[best_from[i]]]
        out.append({
            "full_name": name,
            "language": lang,
            "stargazers_count": stars,
            "html_url": url,          # 之前漏了,导致推荐页的标题链接是坏的
            "similarity": round(float(best_sim[i]), 4),
            "score": round(float(best_sim[i] * popularity), 4),
            "because_of": meta.get(src_id, ("?",))[0],
            "because_kind": kind.get(src_id, "starred"),
            # 下面两个是给"补介绍"用的中间字段,返回前会去掉
            "repo_id": rid,
            "_desc": desc,
        })

    out.sort(key=lambda d: -d["score"])
    top = out[:n]

    # 补上"介绍":从 README 抽的那段(抽不到就用 description)。
    # 只对最终要展示的这几条查 README,不把整张表拉进来。
    from intro import extract_intro
    readmes = db.readmes_for(conn, [d["repo_id"] for d in top])
    for d in top:
        rid = d.pop("repo_id")
        d["intro"] = extract_intro(readmes.get(rid, ""),
                                   d.pop("_desc", None) or "",
                                   d["full_name"])
    return top


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    conn = db.get_conn()
    try:
        items = recommend_for(conn, n)
    except RuntimeError as e:
        print(e)
        return

    print(f"给你推 {len(items)} 个:\n")
    for rank, d in enumerate(items, 1):
        print(f"  {rank:>2}. {d['full_name']}  ({d['language']}, ★{d['stargazers_count']})")
        if d["because_kind"] == "starred":
            why = f"因为你 star 过 {d['because_of']}"
        else:
            why = f"因为你点过感兴趣:{d['because_of']}"
        print(f"      相似度 {d['similarity']:.3f} × 热度 = {d['score']:.3f}   {why}")


if __name__ == "__main__":
    main()
