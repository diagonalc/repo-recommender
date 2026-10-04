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
import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MATRIX_PATH = os.path.join(DATA_DIR, "features.npz")
META_PATH = os.path.join(DATA_DIR, "features_meta.json")
MAP_PATH = os.path.join(DATA_DIR, "map.json")

# 降维到二维用多少邻居、跑多久 —— t-SNE 的两个关键参数
TSNE_PERPLEXITY = 30
TSNE_ITERS = 600

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


def build_map(matrix, ids):
    """把所有仓库从 14471 维压到 2 维,给"口味地图"用。

    ⚠️ **目前没有接进产品**(main() 里那行调用已经注释掉了)。
    理由见 DEVLOG 的"搁置的想法:口味地图" —— 主要是做出来之后,
    用户觉得"看不出所以然",而不是技术上有问题。
    留着是因为里面的实测结论(t-SNE 比 PCA 好得多)是有效的,
    以后想换个形式重做时不用再测一遍。

    产出 data/map.json:每个 repo 一个二维坐标。相似的在图上就挨着。

    **为什么是 t-SNE 而不是 PCA**(实测过的,不是偏好):
        判据是"二维图上挨着的两个点,在原始空间里是不是也真的相似" ——
        对每个 repo 取它在图上最近的 10 个邻居,数有几个也是它真实的 10 个邻居。

            随机图        0.8%
            PCA           4.6%   ← 几乎没结构,画出来是一团好看的噪点
            t-SNE        32.0%   ← 真的能用

        PCA 是线性方法,它保留的是**全局方差最大的方向**;而这堆 TF-IDF 向量
        方差最大的方向跟"谁和谁像"关系不大。t-SNE 专门优化"邻居关系",
        代价是慢(20 秒)而且**只能用来画图** —— 它出的坐标没有距离意义,
        图上的远近不能当相似度用,相似度还得回原始空间算。

        (顺带:两种方法都**不按语言聚**。这是对的 ——
         Python 的 web 框架和 JS 的 web 框架,文本上就是很像。
         图上聚出来的是**主题**,不是语言。)

    ⚠️ t-SNE 是 O(n²) 的。现在 1265 个点没问题(20 秒、内存几百 MB),
    但候选池涨到上万个之后要换办法(先 PCA 降到 50 维再 t-SNE),
    或者改成抽样。真到那一天再说,别提前优化。
    """
    from sklearn.manifold import TSNE

    X = np.asarray(matrix.todense(), dtype=np.float32)
    t0 = time.time()
    coords = TSNE(n_components=2, random_state=0, perplexity=TSNE_PERPLEXITY,
                  init="pca", max_iter=TSNE_ITERS).fit_transform(X)
    print(f"  降维到二维:{X.shape[0]} 个点,耗时 {time.time() - t0:.1f} 秒")

    points = [[int(rid), round(float(x), 3), round(float(y), 3)]
              for rid, (x, y) in zip(ids, coords)]
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MAP_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "method": "tsne",
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "points": points,          # [repo_id, x, y]
        }, f)
    print(f"  坐标写入 {MAP_PATH}")
    return len(points)


def rebuild(limit=DEFAULT_LIMIT, conn=None, quiet=False):
    """重跑一遍向量缓存。返回 (repo 个数, 词表大小)。

    **抽成函数是为了让别的地方也能调** —— 原来它只能在命令行跑,
    于是"什么时候该重建"全靠人记得。而实际有三个地方会改 repos 表:

        · daily_update   每天刷新的榜单
        · sync_stars     把某个用户 star 的仓库并进来(登录时/每日任务里)
        · 全站搜索       并进来搜到的新仓库

    **任何一个改了 repos 而不重建,那些新仓库就没有向量** ——
    表现是"推荐里永远匹配不到它们"。对新用户尤其致命:
    他 star 的往往是些我们没爬过的小仓库,一个都认不出来,
    推荐页就直接报"还没有你的口味数据"。
    """
    def say(*args):
        if not quiet:
            print(*args)

    own_conn = conn is None
    if own_conn:
        conn = db.get_conn()
    try:
        readmes = db.readme_map(conn)
        rows = conn.execute(
            "SELECT id, full_name, description, topics FROM repos "
            "ORDER BY stargazers_count DESC LIMIT ?", (limit,)).fetchall()
        if not rows:
            say("repos 表是空的,先跑 daily_update.py 或 load_raw.py")
            return 0, 0

        with_readme = sum(1 for r in rows if readmes.get(r["id"]))
        say(f"对 {len(rows)} 个 repo 建向量(库里共 {db.count_repos(conn)} 个,"
            f"其中 {with_readme} 个有 README)")

        t0 = time.time()
        ids = [r["id"] for r in rows]
        texts = [build_text(r, readmes.get(r["id"], "")) for r in rows]

        # norm='l2' 是默认值:每行向量归一化成单位长度。
        # 这样"余弦相似度"就等于"点积",后面算相似度直接矩阵相乘,又快又简单。
        vec = TfidfVectorizer(tokenizer=tokenize, token_pattern=None,
                              lowercase=False, min_df=MIN_DF)
        matrix = vec.fit_transform(texts)
        say(f"向量矩阵:{matrix.shape[0]} 个 repo × {matrix.shape[1]} 个词,"
            f"耗时 {time.time() - t0:.1f} 秒")

        os.makedirs(DATA_DIR, exist_ok=True)
        sparse.save_npz(MATRIX_PATH, matrix)
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "repo_ids": ids,
                "limit": limit,
                "vocab_size": matrix.shape[1],
                "built_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
            }, f)
        say(f"缓存写入 {MATRIX_PATH}")
        return len(rows), matrix.shape[1]
    finally:
        if own_conn:
            conn.close()

    # (以前这里会顺手算一遍"口味地图"的二维坐标 —— 那个功能撤掉了,
    #  理由见 DEVLOG 的"搁置的想法:口味地图"。
    #  build_map() 本身留着,想复活的话在 rebuild() 末尾加回来就行,
    #  但注意它要 20 秒,别在没用到的时候白跑。)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LIMIT
    rebuild(limit)


if __name__ == "__main__":
    main()
