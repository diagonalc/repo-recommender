#!/usr/bin/env python3
"""采集"二次元"相关的仓库 —— 给分站 #/acg 用。

用法:
    .venv/bin/python fetch_acg.py            # 每个查询拉 3 页(最多 300 条)
    .venv/bin/python fetch_acg.py 5          # 每个查询拉 5 页
    .venv/bin/python fetch_acg.py --stats    # 只看各查询词各贡献了多少

⚠️ **真正的"内容"是下面那张关键词表,这个脚本只是壳。**
   调它要配着 `--stats` 调:哪个词拉进来的东西不对,就把那个词删掉。
   加词删词都是改一个字符串,不用动代码。

分页/限流/重试全部复用 fetch_repos 里那套(那边踩过坑、修过好几轮)。
"""
import sys
import time

from db import (acg_source_counts, count_acg, get_conn, init_db, save_acg,
                upsert_repos)
from fetch_repos import REQUEST_GAP, fetch_page

PAGES_PER_QUERY = 3          # 每个查询最多拉几页(每页 100 条)
PAGE_SIZE = 100

# ---------------------------------------------------------------------------
# 关键词表
# ---------------------------------------------------------------------------
# 分两类,各有各的问题:
#
#   topic:xxx   仓库作者自己打的标签。**精确度高**,但覆盖不全 ——
#               很多好项目压根没打 topic。
#   名字里含词   覆盖广,但噪音大(下面 "airi in:name" 那条就是例子)。
#
# ⚠️ 实测过的坑(都是量出来的,不是猜的):
#
# ① **topic 也不保证准。** `topic:anime` 按星数排的第一名是
#    juliangarnier/anime(73k★)—— 那是个 **JS 动画引擎**,
#    英文里 anime 就是 animation。而且因为我们按星数排,这种噪音会**浮到最上面**。
#    所以即使是 topic 也要人工过一遍。
#
# ② **中文/日文没法用 `in:name`。** 实测:
#        二次元 in:name   → 0 个      ← 限定词直接被无视,不是"没有匹配"
#        二次元            → 1,286 个  ← 去掉限定词才有
#        catgirl in:name  → 474 个    ← 英文完全正常
#    所以中文只能**不加限定词**地搜。
#
# ③ **但去掉限定词之后,就不能再按星数排了。**
#    不加限定词 = 连描述和 README 一起搜,于是"顺带提过这个词"的爆款会浮上来:
#    实测搜 `二次元` 按星数排,前几名是 one-api、cirosantilli/china-dictatorship……
#    完全不相关;换成按**相关度**排,前几名就对了
#    (acg-faka、anime-character-guessr、ChatWaifu_Mobile)。
#
# **所以中文查询暂时没有收进来** —— 要收的话得给上面这个脚本加一个
# "这条查询别按星数排"的开关(按相关度排),不然拉进来的全是噪音。
# 现在英文 topic 已经能覆盖大部分中文项目(那些项目通常也会打 anime / manga 标签)。
#
# 想要中文项目时,先做那个开关,再把这几个词加回来:
#     二次元(1286)、猫娘(196)、バーチャル(82)
QUERIES = [
    # ---- 英文 topic:最可靠的一批 ----
    "topic:anime",
    "topic:manga",
    "topic:vtuber",
    "topic:waifu",
    "topic:hololive",
    "topic:acg",
    "topic:otaku",
    "topic:catgirl",
    "topic:live2d",
    "topic:voicevox",
    "topic:bangumi",
    "topic:anime-girl",
    "topic:anime-style",
    "topic:virtual-youtuber",
    # 具体作品 / 游戏 —— 粉丝项目特别多,而且往往没打通用的 anime topic
    "topic:genshin-impact",
    "topic:blue-archive",
    "topic:girls-frontline",
    "topic:arknights",
    "topic:touhou",
    "topic:honkai-star-rail",
    "topic:project-sekai",
    "topic:umamusume",
    # ---- 名字里含关键词:覆盖广,噪音也大 ----
    # (只对 ASCII 有效 —— 见上面第 ②③ 条,CJK 不能这么写)
    "waifu in:name",
    "vtuber in:name",
    "catgirl in:name",
    "live2d in:name",
    "voicevox in:name",
]

# 已知的误报。补丁式的排除 —— 不指望搜索本身够准,反正名单本来就小。
BLOCKLIST = {
    "juliangarnier/anime",        # JS 动画引擎:名字里的 anime 是 animation
}


def scan(conn, pages, queries=None):
    """按关键词表扫一遍,写进 acg_repos。

    queries 只用来**单独试某几个词**(调表时很常用)——
    不传就跑完整的关键词表。
    """
    added = 0
    for q in (queries or QUERIES):
        kept = []
        for page in range(1, pages + 1):
            try:
                items = fetch_page(q, page, label=q)
            except RuntimeError as e:
                # 一个词失败不中断整轮 —— 和 daily_update 里同样的原则:
                # 能拿到多少算多少,别让一个环节崩掉整个 job。
                print(f"  [!] {q} 失败,跳过:{e}")
                break
            if not items:
                break
            kept.extend(items)
            if len(items) < PAGE_SIZE:      # 不满一页 = 到头了
                break
            time.sleep(REQUEST_GAP)

        kept = [it for it in kept
                if it.get("full_name") and it["full_name"] not in BLOCKLIST]
        if not kept:
            print(f"  {q}:没拿到东西")
            continue

        upsert_repos(conn, kept)            # 先保证 repos 里有 —— acg_repos 有外键指向它
        ids = [it["id"] for it in kept if it.get("id")]
        added += save_acg(conn, ids, q)
        print(f"  {q}:{len(ids)} 个")

    return added


def main():
    conn = get_conn()
    init_db(conn)

    if "--stats" in sys.argv:
        print(f"二次元集合里现在有 {count_acg(conn)} 个仓库\n")
        print("各查询词各贡献了多少(调表就看这个):")
        for r in acg_source_counts(conn, 60):
            print(f"  {r['n']:>5}  {r['source']}")
        return 0

    pages = PAGES_PER_QUERY
    for a in sys.argv[1:]:
        if a.isdigit():
            pages = int(a)

    # 命令行上直接给查询词的,就**只跑那几个**。
    # 用途:调关键词表时想单独试试某个词效果怎么样,不用等整张表跑完(二十多分钟)。
    #   例:fetch_acg.py "touhou in:name" "原神 in:name"
    extra = [a for a in sys.argv[1:] if not a.isdigit()]
    queries = extra or QUERIES

    print(f"关键词 {len(queries)} 条,每条最多 {pages} 页\n")
    added = scan(conn, pages, queries)

    print(f"\n本轮写入 {added} 条")
    print(f"二次元集合现在共 {count_acg(conn)} 个仓库")
    print("\n下一步:去页面上看一眼,哪条词拉进来的东西不对,"
          "就从 QUERIES 里删掉再跑一次。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
