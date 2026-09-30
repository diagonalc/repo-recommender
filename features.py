#!/usr/bin/env python3
"""P6:把每个 repo 变成 TF-IDF 向量。

用法:
    .venv/bin/python features.py           # 默认对 star 最高的 3000 个建向量
    .venv/bin/python features.py 5000

产出(缓存在 data/ 下,不进 Git):
    data/features.npz         稀疏向量矩阵
    data/features_meta.json   行号 ↔ repo_id 的对应关系

为什么用 TF-IDF 而不是 embedding:
    TF-IDF 不要模型、不要联网、可解释(哪个词权重高一目了然),
    对"技术主题"这种关键词密集的文本已经够用。embedding 更懂语义,
    但要花钱调 API —— 等真的觉得不够准再换,别一上来就上重的。

关键概念:词频 × 逆文档频率
    一个词在某篇文档里出现越多 → 越能代表这篇(TF 高)
    但一个词在所有文档里都出现(the、github、install)→ 它区分不了任何东西(IDF 低)
    两者相乘,留下的就是"这篇文档的特征词"。
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import jieba
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MATRIX_PATH = os.path.join(DATA_DIR, "features.npz")
META_PATH = os.path.join(DATA_DIR, "features_meta.json")

DEFAULT_LIMIT = 3000
MIN_DF = 2          # 至少在 2 篇文档里出现过的词才要(只出现一次的多半是噪音)

# 技术文本里到处都是、但完全区分不了主题的词
STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "that", "this", "is", "are", "from",
    "can", "will", "not", "use", "using", "used", "github", "com", "http",
    "https", "www", "org", "more", "all", "any", "our", "it's", "its",
    "code", "project", "repo", "repository", "readme", "install", "installation",
    "documentation", "docs", "example", "examples", "feature", "features",
    "支持", "使用", "一个", "我们", "可以", "这个", "项目", "功能", "安装",
    "文档", "示例", "以及", "提供", "基于", "通过", "进行", "需要", "实现"
}

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#._-]*")   # 保住 c++ / c# / node.js / scikit-learn 这类词
CJK_RE = re.compile(r"[一-鿿]")


def tokenize(text):
    """中英混排分词。

    jieba 负责中文切词;英文部分它也能切,但我们再用正则过一遍,
    免得 c++、node.js、scikit-learn 这种技术词被切碎 —— 这些恰恰是最有区分度的词。
    """
    tokens = []
    for chunk in jieba.cut(text.lower()):
        chunk = chunk.strip()
        if not chunk:
            continue
        if CJK_RE.search(chunk):
            if len(chunk) >= 2:        # 中文单字太泛("的""和"),两个字起
                tokens.append(chunk)
        else:
            tokens.extend(TOKEN_RE.findall(chunk))
    return [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]


def build_text(repo_row, readme):
    """把一个 repo 的所有文本拼成一篇"文档"。

    full_name 也拼进去 —— 仓库名往往就是最精炼的主题词
    (langchain、ollama、yt-dlp 本身就说明了一切)。
    """
    parts = [repo_row["full_name"] or "", repo_row["description"] or ""]
    try:
        parts.extend(json.loads(repo_row["topics"] or "[]"))
    except (TypeError, ValueError):
        pass
    parts.append(readme or "")
    return " ".join(parts)


def load_features():
    """加载缓存。返回 (matrix, repo_ids),行号 i 对应 repo_ids[i]。"""
    if not os.path.exists(MATRIX_PATH):
        raise SystemExit("还没有向量缓存,先跑:.venv/bin/python features.py")
    matrix = sparse.load_npz(MATRIX_PATH)
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)
    return matrix, meta["repo_ids"]


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LIMIT

    conn = db.get_conn()
    readmes = db.readme_map(conn)
    rows = conn.execute(
        "SELECT id, full_name, description, topics FROM repos "
        "ORDER BY stargazers_count DESC LIMIT ?", (limit,)).fetchall()
    if not rows:
        print("repos 表是空的,先跑 daily_update.py 或 load_raw.py")
        return

    with_readme = sum(1 for r in rows if readmes.get(r["id"]))
    print(f"对 {len(rows)} 个 repo 建向量(库里共 {db.count_repos(conn)} 个,"
          f"其中 {with_readme} 个有 README)")

    t0 = time.time()
    ids = [r["id"] for r in rows]
    texts = [build_text(r, readmes.get(r["id"], "")) for r in rows]

    # norm='l2' 是默认值:每行向量归一化成单位长度。
    # 这样"余弦相似度"就等于"点积",后面算相似度直接矩阵相乘,又快又简单。
    vec = TfidfVectorizer(tokenizer=tokenize, token_pattern=None,
                          lowercase=False, min_df=MIN_DF)
    matrix = vec.fit_transform(texts)

    print(f"向量矩阵:{matrix.shape[0]} 个 repo × {matrix.shape[1]} 个词")
    print(f"非零元素 {matrix.nnz} 个 —— 稀疏度 "
          f"{matrix.nnz / (matrix.shape[0] * matrix.shape[1]):.3%}"
          f"(所以必须用稀疏矩阵存,普通二维数组会撑爆内存)")
    print(f"耗时 {time.time() - t0:.1f} 秒")

    os.makedirs(DATA_DIR, exist_ok=True)
    sparse.save_npz(MATRIX_PATH, matrix)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "repo_ids": ids,
            "limit": limit,
            "vocab_size": matrix.shape[1],
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, f)
    print(f"缓存写入 {MATRIX_PATH}")


if __name__ == "__main__":
    main()
//