#!/usr/bin/env python3
"""给"作者自己没设 topics"的 repo 自动补标签。

用法:
    .venv/bin/python autotag.py

策略(零手工):
    1. 语言必进 —— 它可靠,而且是筛选时最常用的一类标签
    2. 再从 description + README 里取 TF-IDF 权重最高的几个词当标签
       (权重高 = 这个词最能把"这个 repo"和别的区分开)
    3. 合起来最多 4 个

结果写进 auto_tags 表而不是 repos.topics —— 原因见 schema.sql 里的注释:
写回 topics 会被每天的 daily_update 抹掉。
"""
from sklearn.feature_extraction.text import TfidfVectorizer

import db
from features import STOPWORDS, build_text, tokenize

MAX_TAGS = 4
MIN_TERM_LEN = 3

# 自动打标签特有的噪音词:它们在 README 里到处都是,但说明不了"这个项目是干什么的"。
# 主要是赞助平台、CI 服务、社交链接、以及各种模板化的段落标题。
TAG_NOISE = {
    "authors", "author", "contributors", "contributor", "license", "licence",
    "version", "versions", "release", "releases", "changelog", "contributing",
    "sponsor", "sponsors", "sponsorship", "donate", "donation", "funding",
    "tidelift", "patreon", "opencollective", "saucelabs", "travis", "circleci",
    "codecov", "coveralls", "npmjs", "gitter", "discord", "twitter", "mastodon",
    "stackoverflow", "website", "blog", "wiki", "pricing", "plan", "plans",
    "support", "issues", "pull", "commit", "branch", "merge", "readme",
    "requirements", "getting", "started", "usage", "quickstart",
}


def lang_tag(language):
    """把语言名变成标签写法:Jupyter Notebook → jupyter-notebook。"""
    lang = (language or "").strip().lower()
    return lang.replace(" ", "-") if lang else ""


def main():
    conn = db.get_conn()
    db.init_db(conn)

    rows = db.repos_without_topics(conn)
    print(f"没设 topics 的 repo:{len(rows)} 个")
    if not rows:
        return

    readmes = db.readme_map(conn)
    docs = [build_text(r, readmes.get(r["id"], "")) for r in rows]

    # 只在这批 repo 内部算词频。样本不大(一百多个),所以 min_df=1 全都要。
    vec = TfidfVectorizer(tokenizer=tokenize, token_pattern=None,
                          lowercase=False, min_df=1, max_features=20000)
    matrix = vec.fit_transform(docs)
    terms = vec.get_feature_names_out()

    db.clear_auto_tags(conn)          # 重跑时先清空,避免旧的残留
    total = 0
    samples = []

    for i, r in enumerate(rows):
        tags = []
        lang = lang_tag(r["language"])
        if lang:
            tags.append(lang)

        # 所有者名字几乎每篇 README 都会出现(jashkenas/backbone → "jashkenas"),
        # 但它不是"这个项目是干什么的",挡掉
        owner = (r["full_name"] or "").split("/")[0].lower()

        weights = matrix.getrow(i).toarray().ravel()
        for j in weights.argsort()[::-1]:       # 按权重从高到低
            if weights[j] <= 0 or len(tags) >= MAX_TAGS:
                break
            term = terms[j]
            if len(term) < MIN_TERM_LEN or term in STOPWORDS or term in TAG_NOISE:
                continue
            if term == owner or term in tags:
                continue
            if any(c.isdigit() for c in term):  # 版本号之类(4.1、2024)不是标签
                continue
            tags.append(term)

        db.save_auto_tags(conn, r["id"], tags)
        total += len(tags)
        if len(samples) < 12:
            samples.append((r["full_name"], tags))

    print(f"写好 {total} 个标签 → auto_tags 表共 {db.count_auto_tags(conn)} 行")
    print(f"现在有标签的 repo:{db.tag_cloud_count(conn)} / {db.count_repos(conn)}")
    print("\n抽样看自动打的标签:")
    for name, tags in samples:
        print(f"  {name:<48} {' '.join(tags)}")


if __name__ == "__main__":
    main()
