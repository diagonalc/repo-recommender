#!/usr/bin/env python3
"""P6:抓 README 原文 —— 内容相似要用的文本素材。

用法:
    .venv/bin/python fetch_readmes.py          # 抓所有还没抓过的
    .venv/bin/python fetch_readmes.py 300      # 这次最多抓 300 个

为什么抓 README:
    description 只有一句话,topics 只有几个词。README 才真正讲清"这个 repo 在干什么"。
    相似度算得准不准,基本取决于文本素材够不够。

两个刻意的处理:
  1. 按 star 从高到低抓 —— 先把热门的抓了,冷门 repo 的相似度没人会看
  2. 没有 README 的也存一条空记录 —— 否则每次跑都会重新去试它,白费额度
"""
import re
import sys
import time

import requests

from db import (count_readmes, get_conn, init_db, repos_for_readme,
                save_readme)
from fetch_repos import TOKEN

API = "https://api.github.com/repos/{}/readme"
MAX_CHARS = 4000      # 详情页要能读,给得宽一点(1265 个 × 4000 ≈ 5MB,库里放得下)
GAP = 0.4             # 认证后 core 限额 5000/小时,这个节奏很宽裕

TAG_RE = re.compile(r"<[^>]+>")     # HTML 标签
SPACE_RE = re.compile(r"[ \t]+")    # 行内连续空白

# 注意:这里刻意**保留换行**。
# 第一版把换行也压成了空格,结果:① 介绍没法按段落抽,只能瞎猜 ② 详情页读起来是一坨。
# 换行是免费的结构信息,压掉它等于自己把线索扔了。


def clean(text):
    """去 HTML 标签 → 行内空白压成一个空格 → 连续空行压成一个 → 截断。"""
    text = TAG_RE.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    out = []
    for line in text.split("\n"):
        line = SPACE_RE.sub(" ", line).strip()
        if not line and out and not out[-1]:      # 连续空行只留一个
            continue
        out.append(line)
    return "\n".join(out).strip()[:MAX_CHARS]


def fetch_readme(full_name):
    """拿到 README 原文;这 repo 没有 README 就返回 None(404 是正常情况,不是错误)。"""
    headers = {"Accept": "application/vnd.github.raw"}
    if TOKEN:
        headers["Authorization"] = f"token {TOKEN}"
    r = requests.get(API.format(full_name), headers=headers, timeout=30)
    if r.status_code == 200:
        return r.text
    if r.status_code == 404:
        return None
    raise RuntimeError(f"{full_name}: HTTP {r.status_code}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    refresh = "--refresh" in sys.argv        # 重抓已有的(改了 clean() 规则后要用)
    limit = int(args[0]) if args else 5000

    conn = get_conn()
    init_db(conn)

    todo = repos_for_readme(conn, limit, refresh=refresh)
    print(f"待抓 {len(todo)} 个(库里已有 {count_readmes(conn)} 个"
          f"{',refresh 模式' if refresh else ''})")
    if not todo:
        return

    ok = empty = fail = 0
    for i, row in enumerate(todo, 1):
        try:
            raw = fetch_readme(row["full_name"])
        except RuntimeError as e:
            print(f"  [!] {e}")
            fail += 1
            continue

        if raw is None:
            save_readme(conn, row["id"], "")     # 存空,免得下次重试
            empty += 1
        else:
            save_readme(conn, row["id"], clean(raw))
            ok += 1

        if i % 100 == 0:
            print(f"  {i}/{len(todo)}  (成功 {ok} / 无README {empty} / 失败 {fail})")
        time.sleep(GAP)

    print(f"完成:成功 {ok},无 README {empty},失败 {fail},库里共 {count_readmes(conn)} 个")


if __name__ == "__main__":
    main()
