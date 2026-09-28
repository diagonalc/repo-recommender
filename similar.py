#!/usr/bin/env python3
"""P6:给一个 repo,找最像它的 Top-N。

用法:
    .venv/bin/python similar.py langchain-ai/langchain
    .venv/bin/python similar.py langchain-ai/langchain 10

原理一句话:向量已经归一化过,所以"余弦相似度"就是"点积" ——
拿目标那行去乘整个矩阵,得到的一列分数就是它和每个 repo 的相似度。
"""
import sys

import numpy as np

import db
from features import load_features


def similar_rows(matrix, ids, repo_id, n=10):
    """和 repo_id 最像的 n 个。返回 [(repo_id, 相似度), ...],不含它自己。

    抽成函数是因为详情页接口也要用同一份逻辑,不能两处各写一遍。
    """
    pos = {rid: i for i, rid in enumerate(ids)}
    if repo_id not in pos:
        return []
    idx = pos[repo_id]
    # 向量已 L2 归一化,所以点积就是余弦相似度
    scores = (matrix @ matrix[idx].T).toarray().ravel()
    scores[idx] = -1.0                      # 把自己排掉
    top = np.argsort(-scores)[:n]
    return [(ids[i], float(scores[i])) for i in top if scores[i] > 0]


def main():
    if len(sys.argv) < 2:
        print("用法:.venv/bin/python similar.py <owner/repo> [N]")
        return
    target = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    matrix, ids = load_features()

    conn = db.get_conn()
    # 注意:ids 里存的是 repo_id(整数),不是 full_name。
    # 所以要先拿 full_name 去库里查出 id,再拿 id 找行号 —— 这两步别混。
    repo_id = db.find_repo_id(conn, target)
    if repo_id is None:
        print(f"库里没有 {target}")
        return

    sims = similar_rows(matrix, ids, repo_id, n)
    if not sims:
        print(f"{target} 不在向量缓存里(只对 star 最高的 {len(ids)} 个建了向量)")
        return

    print(f"和 {target} 最像的 {n} 个:\n")
    for rank, (rid, score) in enumerate(sims, 1):
        row = conn.execute(
            "SELECT full_name, language, stargazers_count FROM repos WHERE id = ?",
            (rid,)).fetchone()
        if row is None:
            continue
        print(f"  {rank:>2}. {score:.3f}  {row['full_name']} "
              f"({row['language']}, ★{row['stargazers_count']})")


if __name__ == "__main__":
    main()
