"""临时:验证名字限定搜索 + 介绍截断。用完删。"""
import requests

import db
from intro import extract_intro

API = "http://127.0.0.1:8000"

print("=== 1) 全站搜索改成只匹配 repo 名字 ===")
for q in ["terminal file manager", "file-manager", "yazi", "vim"]:
    d = requests.get(f"{API}/api/search",
                     params={"q": q, "scope": "github", "limit": 6}, timeout=60).json()
    names = [it["full_name"] for it in d["items"]]
    hit = sum(1 for n in names if q.lower().replace(" ", "") in n.lower().replace("-", ""))
    print(f"  q={q!r:<24} → {d['count']} 个,名字真含关键词的: {hit}/{len(names)}")
    for n in names[:5]:
        print(f"       {n}")

print()
print("=== 2) 介绍长度(应该都 <= 223:220 + 省略号)===")
conn = db.get_conn()
rows = conn.execute("""
    SELECT r.full_name, r.description, m.content FROM repos AS r
    LEFT JOIN readmes AS m ON m.repo_id = r.id
    ORDER BY length(r.description) DESC LIMIT 5""").fetchall()
for r in rows:
    intro = extract_intro(r["content"] or "", r["description"] or "", r["full_name"])
    print(f"  desc {len(r['description'] or ''):>4} 字符 → intro {len(intro):>4} 字符  {r['full_name'][:38]}")
    if len(intro) > 230:
        print("      ^^^ 超了!")
