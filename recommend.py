#!/usr/bin/env python3
"""P6:我的推荐 —— 从"我 star 过的 + 我点过感兴趣的"出发,找像它们、但我还没 star 的。

用法:
    .venv/bin/python recommend.py          # Top 20
    .venv/bin/python recommend.py 10

打分公式(刻意做得简单可调):
    最终分 = 加权相似度 × 热度系数
    加权相似度 = max(信号权重 × 与那个信号的余弦相似度)
    信号权重   = star 1.0,点"感兴趣" 0.5
    热度系数   = 1 + 0.1 × log10(星数)

为什么要乘热度:
    光看相似度,会推出一堆"很像但没人用、早就停更"的 repo。
    乘一个随星数缓慢增长(取对数)的系数,让热门略占优,又不会让大 repo 通吃 ——
    取对数就是为了压住"48 万星 vs 5 百星"这种量级碾压。

为什么 star 比"感兴趣"重:
    star 是**主动收藏** —— 你专门去点了星,还会在 GitHub 上一直看到它。
    "感兴趣"只是在这个站上随手点了一下,门槛低得多,也更容易点错。
    两者都算正向信号,但强度不一样,不该一视同仁。

为什么每 10 个位置插一个"探索位":
    只按相似度排,结果会越来越窄 —— 你 star 过的都是同一类东西,
    推出来的就都是同一类,最后整页都是"你已经知道的东西的变体"。
    这就是信息茧房。留一小部分位置给"不像你、但确实有很多人在用/在涨"的,
    是在**主动打破它**。详见 _explore_items()。

为什么每条推荐都带"因为你 star 过 X":
    推荐结果不可解释就没法调。看到"为什么推它",你才能判断是相似度算歪了,
    还是你自己的口味数据太少 —— 否则只能盲调权重。
"""
import json
import math
import os
import sys

import numpy as np

import db
from features import load_features

# ---------------- 可调参数 ----------------
# 集中放这儿:调推荐效果基本就是调这几个数,别让它们散在代码各处。
POPULARITY_WEIGHT = 0.1     # 热度系数里的那个 0.1
STAR_WEIGHT = 1.0           # star 的信号权重
LIKE_WEIGHT = 0.5           # "感兴趣"的信号权重(半个 star)
EXPLORE_EVERY = 10          # 每几个位置插一个探索位(10 ≈ 10%)
EXPLORE_MAX_SIM = 0.10      # 相似度高于这个就不算"探索"了 —— 它本来就"像"
GROWTH_WEIGHT = 1.0         # 探索位排序时,增长速度相对人气的分量


def _explore_items(conn, ids, sim_to_closest, my_set, banned, meta):
    """挑"探索位"的候选:不像你、但人气高或在涨。

    两个条件都要满足:
      1. **相似度低** —— 相似度高的本来就该出现在正常推荐里,
         把它标成"探索"是自欺欺人
      2. **人气高 / 涨得快** —— 不然就是随机噪音,推给用户是浪费他的时间

    ⚠️ 判断"像不像"用的是 `sim_to_closest`(和**所有**信号里最像的那个的余弦),
    **不是** `best_sim`(贡献最大的那个信号的余弦)。
    两者在加了权重之后会不一样:一个 0.5 的 like 加权成 0.25,
    会输给一个 0.3 的 star,于是 best_sim 是 0.3、而最像的其实是那个 0.5 的。
    问"这个仓库像不像你的口味",该看最像的那个 —— 用 best_sim 会漏掉
    "其实很像、只是权重低"的仓库,把该排除的放进了探索位。

    排序用 log 而不是线性:star 从几百到几十万、增量从 0 到几千,
    线性比的话大仓库会通吃,**增长的信号会被完全压掉** ——
    那"快速增长"这个词就白写了。

    ⚠️ 阈值 EXPLORE_MAX_SIM=0.10 是照着实测分布定的:
    本库相似度的 P50≈0.08、P75≈0.12、P95≈0.22。
    取 0.10 大致是"下半截",既真的"不像",又还剩几百个候选可选。
    库变了要重新看一下这个数(改 features.py 的词表就会变)。
    """
    # 增长数据:最新两个快照日之间的 star 增量
    growth = {}
    dates = db.snapshot_dates(conn)
    if len(dates) >= 2:
        growth = {r["id"]: r["delta"] for r in db.growth_rows(conn, dates[0], dates[1])}

    pool = []
    for i, rid in enumerate(ids):
        if i in my_set or i in banned:
            continue
        if sim_to_closest[i] >= EXPLORE_MAX_SIM:
            continue
        stars = meta.get(rid, ("?", None, 0))[2] or 0
        delta = growth.get(rid)
        # log10(max(x,1)):star=1 和 star=0 得到 0,不会因为 log(0) 炸掉
        heat = math.log10(max(stars, 1))
        if delta is not None:
            heat += GROWTH_WEIGHT * math.log10(max(delta, 1))
        pool.append((heat, i, rid))

    pool.sort(key=lambda x: -x[0])
    return pool, growth


def _merge_explore(exploit, explore, every=EXPLORE_EVERY):
    """把探索位均匀插进主列表,并去重。

    ⚠️ 必须是**确定性**的。推荐靠 offset 分页(滚到底自动加载下一批),
    如果每次算出来的顺序不一样,翻页就会重复或漏内容 ——
    而且用户完全看不出来是哪里错了,只会觉得"这个怎么又出现了一次"。
    所以插在**固定位置**上,同样的输入永远得到同样的顺序。

    ⚠️ 位置按**输出**数,不是按主列表的序号数。
    一开始写成了"每第 10 个主列表项之前插一个",结果是第 10、21、32…位
    (间距 11)—— 因为每插进去一个,后面所有位置都被挤后了一位。
    看着差不多,但 `EXPLORE_EVERY = 10` 这个常量就没法照字面理解了。

    多余的探索位**丢掉**,不堆到末尾:堆末尾的话,主列表一短
    (比如信号很少的用户),后半段就全成了探索位 ——
    那不叫"偶尔加点",那是变成另一个页面了。
    """
    out, ei, xi = [], 0, 0
    while ei < len(exploit) and xi < len(explore):
        if (len(out) + 1) % every == 0:
            out.append(explore[xi])
            xi += 1
        else:
            out.append(exploit[ei])
            ei += 1
    out.extend(exploit[ei:])

    seen, final = set(), []
    for it in out:
        rid = it["repo_id"]
        if rid in seen:          # 一个 repo 可能既在探索池里又在主列表尾部
            continue
        seen.add(rid)
        final.append(it)
    return final


def recommend_for(conn, user_id, n=20, offset=0, sort="similarity"):
    """算推荐列表。命令行和 HTTP 接口共用这一份逻辑(别写两遍)。

    offset 用来"换一批":推荐是按分数排好的长列表,取第 offset 个开始的 n 个。
    这样点一次刷新就往后翻一段,每次都是没看过的新 repo ——
    比重新算一遍强(重算结果还是一样,等于没换)。

    返回 list[dict],已按分数从高到低排好。
    没有向量缓存或没有口味信号时抛 RuntimeError,由调用方决定怎么呈现
    (命令行打印一行,HTTP 接口转成 409)。
    """
    try:
        matrix, ids = load_features()      # 没缓存时它抛 SystemExit
    except SystemExit as e:
        raise RuntimeError(str(e))

    pos = {rid: i for i, rid in enumerate(ids)}
    opinions = db.latest_opinions(conn, user_id)

    # 口味信号 = 这个人 star 过的 + 他点过"感兴趣"的。
    # 两者都是正向偏好,但**强度不同**:star 是主动收藏,"感兴趣"只是随手一点。
    # 区别体现在下面的 weights 上。
    starred = db.starred_repo_ids(conn, user_id)
    liked = {rid for rid, act in opinions.items() if act == "interested"}
    positive = starred | liked

    # 记住每个正向信号是"star 来的"还是"点击来的" —— 推荐理由得说实话。
    # 既 star 又点过感兴趣的,按 star 算(更强的信号)。
    kind = {rid: "starred" for rid in starred}
    for rid in liked:
        kind.setdefault(rid, "interested")

    my_pos = [pos[r] for r in positive if r in pos]
    if not my_pos:
        # 新用户一定会撞上这条 —— 提示要面向网页用户,别丢一句命令行脚本给他。
        # 注意:别在这里承诺"会自动同步 star" —— 现在已经会了(sync_all.py),
        # 但同步是每天跑一次,刚登录的人还是可能还没有数据。
        raise RuntimeError("还没有你的口味数据。等每日同步跑一次,"
                           "或先去 Trending 页点几个[感兴趣]试试")

    my_ids = [ids[i] for i in my_pos]

    # (我的 k 个正向信号) × (全部 repo) → 相似度矩阵
    sims = np.asarray((matrix[my_pos] @ matrix.T).todense())

    # ★ star 的权重比"感兴趣"高。
    #
    # 关键:加权要发生在**取最大值之前**。
    # 先取 max 再乘权重是没有意义的 —— 最大值乘一个常数还是最大值,
    # 谁大谁小完全不变。(这个函数原来的注释说"算的是最像的那个信号,
    # 加权意义不大",那个说法**只在'先 max 后加权'的前提下成立**。)
    # 所以这里是 max(w_s × sim_s),而不是 w × max(sim_s)。
    weights = np.array([STAR_WEIGHT if kind[rid] == "starred" else LIKE_WEIGHT
                        for rid in my_ids])
    weighted = sims * weights[:, None]

    best_idx = weighted.argmax(axis=0)          # 每个候选:贡献最大的那个信号
    ar = np.arange(len(ids))
    best_w = weighted[best_idx, ar]             # 加权后的分(排序用)
    best_sim = sims[best_idx, ar]               # 那个信号的原始余弦(展示用)

    # "和所有信号里**最像**的那个"的相似度。
    #
    # 它和 best_sim 不是一回事:best_sim 是"**贡献最大**的那个信号"的相似度,
    # 而加权之后贡献最大的不一定是最像的 ——
    # 一个 0.5 的 like(加权 0.25)会输给一个 0.3 的 star(加权 0.30)。
    #
    # 两个数各有各的用处,别混:
    #   best_sim  → 展示"和你 star 过的 X 有多像"(要跟推荐理由里那个 X 对得上)
    #   raw_max   → 判断"像不像你的口味"(探索位筛选用)
    raw_max = sims.max(axis=0)

    # 负向信号:当前态度是"不感兴趣"的,直接排除。
    # 关键:用 latest_opinions(每个 repo 的最新一条),不是"曾经点过" ——
    # 你改主意了,推荐就得跟着改。
    banned = {pos[rid] for rid, act in opinions.items()
              if act == "not_interested" and rid in pos}
    my_set = set(my_pos)

    meta = {row["id"]: (row["full_name"], row["language"], row["stargazers_count"],
                        row["description"], row["html_url"], row["topics"])
            for row in conn.execute(
                "SELECT id, full_name, language, stargazers_count, description, "
                "html_url, topics FROM repos")}

    def topics_of(rid):
        try:
            return json.loads(meta.get(rid, (None,) * 6)[5] or "[]")
        except (TypeError, ValueError):
            return []

    out = []
    for i, rid in enumerate(ids):
        if i in my_set or i in banned or best_w[i] <= 0:
            continue
        name, lang, stars, desc, url, _ = meta.get(rid, ("?", None, 0, None, None, None))
        popularity = 1 + POPULARITY_WEIGHT * np.log10(max(stars, 1))
        # best_idx[i] 是"我的第几个正向信号",要转回 repo_id 再转成名字
        src_id = my_ids[best_idx[i]]
        out.append({
            "full_name": name,
            "language": lang,
            "stargazers_count": stars,
            "html_url": url,
            "topics": topics_of(rid),
            "similarity": round(float(best_sim[i]), 4),   # 原始余弦,给用户看的
            "score": round(float(best_w[i] * popularity), 4),
            "because_of": meta.get(src_id, ("?",))[0],
            "because_kind": kind.get(src_id, "starred"),
            # 下面两个是给"补介绍"用的中间字段,返回前会去掉
            "repo_id": rid,
            "_desc": desc,
        })

    # 排序放在服务端做,而不是前端。
    # 原因:前端是"滚到底自动加载下一批",每批是**追加**的 ——
    # 如果每批在浏览器里各自排序再拼起来,整体顺序就乱了
    # (第 2 批里 star 很高的仓库会排在第一批后面)。
    # 服务端对**完整列表**排好再切片,翻多少页顺序都是对的。
    if sort == "stars":
        out.sort(key=lambda d: -d["stargazers_count"])
    elif sort == "name":
        out.sort(key=lambda d: d["full_name"])
    else:                                   # "similarity" 就是推荐分本身
        out.sort(key=lambda d: -d["score"])

    # ---- 探索位:只在默认排序下加 ----
    # 按 star / 名称排序是用户**显式**要的"给我按这个排",插一条不按那个序的
    # 只会让人困惑;而且那种排序本来就不个性化,也就无所谓茧房。
    if sort == "similarity":
        pool, growth = _explore_items(conn, ids, raw_max, my_set, banned, meta)
        explore = []
        for heat, i, rid in pool:
            name, lang, stars, desc, url, _ = meta.get(
                rid, ("?", None, 0, None, None, None))
            explore.append({
                "full_name": name,
                "language": lang,
                "stargazers_count": stars,
                "html_url": url,
                "topics": topics_of(rid),
                # 探索位**没有** similarity / score —— 不假装它"像你"。
                # 前端据此显示"换换口味"而不是一个相似度数字。
                "because_of": None,
                "because_kind": "explore",
                "delta": growth.get(rid),      # 最近这几天涨了多少(没有就是 None)
                "repo_id": rid,
                "_desc": desc,
            })
        out = _merge_explore(out, explore)

    top = out[offset:offset + n]

    # 补上"介绍":从 README 抽的那段(抽不到就用 description)。
    # 只对最终要展示的这几条查 README,不把整张表拉进来。
    from intro import extract_intro
    ids_top = [d["repo_id"] for d in top]
    readmes = db.readmes_for(conn, ids_top)
    auto = db.auto_tags_for(conn, ids_top)
    ccount = db.comment_counts(conn, ids_top)

    for d in top:
        rid = d.pop("repo_id")
        d["intro"] = extract_intro(readmes.get(rid, ""),
                                   d.pop("_desc", None) or "",
                                   d["full_name"])
        d["comment_count"] = ccount.get(rid, 0)
        # 自动补的标签也要并进来 —— 否则同一个 repo 在 Trending 页有标签、
        # 到推荐页就没标签了,同一个字段两处口径不一致最容易被当成 bug。
        merged = list(d.get("topics") or [])
        for x in auto.get(rid, []):
            if x not in merged:
                merged.append(x)
        d["topics"] = merged

    return top


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    # 命令行默认看第一个用户(这是给你自己调试用的,不是对外接口)
    user_id = int(os.environ.get("REPOS_USER", "1"))
    conn = db.get_conn()
    try:
        items = recommend_for(conn, user_id, n)
    except RuntimeError as e:
        print(e)
        return

    print(f"给你推 {len(items)} 个:\n")
    for rank, d in enumerate(items, 1):
        if d["because_kind"] == "explore":
            grew = f",近两天 +{d['delta']}" if d.get("delta") else ""
            print(f"  {rank:>2}. {d['full_name']}  ({d['language']}, "
                  f"★{d['stargazers_count']})")
            print(f"      ✨ 换换口味(不像你以前 star 的{grew})")
            continue
        print(f"  {rank:>2}. {d['full_name']}  ({d['language']}, ★{d['stargazers_count']})")
        if d["because_kind"] == "starred":
            why = f"因为你 star 过 {d['because_of']}"
        else:
            why = f"因为你点过感兴趣:{d['because_of']}"
        print(f"      相似度 {d['similarity']:.3f} × 热度 = {d['score']:.3f}   {why}")


if __name__ == "__main__":
    main()
