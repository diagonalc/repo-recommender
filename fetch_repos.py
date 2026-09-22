#!/usr/bin/env python3
"""P1:按语言拉 GitHub repo 候选池,存到 data/raw/。

用法:
    export GITHUB_TOKEN=ghp_xxx      # 没有也能跑,但很快会被限流
    python3 fetch_repos.py

脚本会:按语言(每个语言翻几页)拉 repo,每页存成一个 JSON 文件。
重复运行不会重拉已存在的页 —— 这就是"断点续跑"。
"""
import json
import os
import time

import requests

# ---------------- 配置 ----------------
LANGUAGES = ["python", "javascript", "typescript", "rust", "go", "java"]
PAGES_PER_LANG = 2                     # 每页最多 100 个 → 6 语言 × 2 页 ≈ 1200 个
BASE_URL = "https://api.github.com/search/repositories"
RAW_DIR = "data/raw"
TOKEN = os.environ.get("GITHUB_TOKEN")  # 从环境变量读,绝不写死在代码里

# 每个 repo 至少保留这些字段(P2 入库要用)
KEEP_FIELDS = ["id", "full_name", "description", "language",
               "topics", "stargazers_count", "pushed_at", "html_url"]

# 每次请求之间睡多久(秒)—— 这个值是被"限流"直接决定的:
#   认证后 search 接口 ≈30 次/分钟 → 睡 2 秒足够(12 次请求远用不完)
#   未认证只有 10 次/分钟       → 必须睡 ≥7 秒,否则 2 秒发一个 = 30 次/分钟,必撞
REQUEST_GAP = 2.0 if TOKEN else 7.0
MAX_RETRIES = 4     # 撞限流后最多重试几次
MAX_WAIT = 120      # 单次等待上限(秒),别让脚本睡死


def build_params(lang, page):
    """拼查询参数:按语言筛 + 按 star 降序 + 翻到第 page 页。"""
    return {
        "q": f"language:{lang}",
        "sort": "stars",
        "order": "desc",
        "per_page": 100,   # 每页最多 100
        "page": page,
    }


def _message(resp):
    """安全取出响应体里的 message(响应可能不是 JSON,别让它崩)。"""
    try:
        return resp.json().get("message", "")
    except ValueError:
        return ""


def wait_seconds(resp):
    """撞限流了,算该等多少秒。

    两种限流要区别对待(这是这次踩坑学到的):
      - secondary rate limit(响应头有 Retry-After):GitHub 的原话是
        "wait a few minutes",所以它给的秒数要当下限,不能睡 2 秒就冲
      - primary rate limit(额度真用完,剩余=0):等额度窗口重置
        (X-RateLimit-Reset 是"重置时刻",减现在 = 还要等多久)
    """
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        return min(max(int(retry_after), 30), MAX_WAIT)      # 二级限流至少等 30s
    reset = resp.headers.get("X-RateLimit-Reset")
    if reset:
        return min(max(int(reset) - int(time.time()), 5), MAX_WAIT)
    return 30


def fetch_page(lang, page):
    """拉某一语言某一页。

    成功 → 返回 repo 列表(空列表表示这语言没有更多了)。
    重试多次仍被限流 → 抛 RuntimeError,让上层停下来。
    """
    headers = {"Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"token {TOKEN}"

    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.get(BASE_URL, headers=headers,
                            params=build_params(lang, page), timeout=30)
        remaining = resp.headers.get("X-RateLimit-Remaining")
        print(f"  {lang} p{page} → HTTP {resp.status_code}(剩余额度 {remaining})")

        if resp.status_code == 200:
            return resp.json().get("items", [])

        # 403/429 可能是"限流",也可能是"真没权限" —— 靠响应头和 message 区分
        if resp.status_code in (403, 429):
            msg = _message(resp)
            rate_limited = (resp.headers.get("Retry-After") is not None
                            or remaining == "0"
                            or "rate limit" in msg.lower())
            if rate_limited and attempt < MAX_RETRIES:
                wait = wait_seconds(resp)
                print(f"    撞限流:{msg};等 {wait}s 再试(第{attempt}次)")
                time.sleep(wait)
                continue
            raise RuntimeError(f"限流/权限问题:{resp.status_code} {msg}")

        raise RuntimeError(f"未知错误:{resp.status_code}")

    raise RuntimeError("重试次数用完仍失败")


def save_page(lang, page, repos):
    """把一页 repo 精简成 KEEP_FIELDS,存成 data/raw/{lang}_{page}.json。"""
    os.makedirs(RAW_DIR, exist_ok=True)
    path = os.path.join(RAW_DIR, f"{lang}_{page}.json")
    slim = [{k: r.get(k) for k in KEEP_FIELDS} for r in repos]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, indent=2)
    print(f"    存了 {len(slim)} 个 → {path}")


def main():
    if not TOKEN:
        print("[提醒] 没设 GITHUB_TOKEN:未认证搜索限流只有 10 次/分钟,很容易被拒。")

    total = 0
    for lang in LANGUAGES:
        for page in range(1, PAGES_PER_LANG + 1):
            path = os.path.join(RAW_DIR, f"{lang}_{page}.json")
            if os.path.exists(path):        # 已拉过 → 跳过(断点续跑)
                print(f"  跳过 {path}(已存在)")
                continue

            try:
                repos = fetch_page(lang, page)
            except RuntimeError as e:
                print(f"[停] {e}")
                print(f"当前已入库 {total} 个;下次再跑会自动接着拉。")
                return

            if not repos:                   # 空 = 这语言到头了
                print(f"  {lang} 没有更多了")
                break

            save_page(lang, page, repos)
            total += len(repos)
            time.sleep(REQUEST_GAP)         # 单线程睡一下,别撞限流

    print(f"完成:共入库 {total} 个 repo → {RAW_DIR}/")


if __name__ == "__main__":
    main()
