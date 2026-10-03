#!/usr/bin/env python3
"""数据库备份。

⚠️ **不能直接 cp 那个 .db 文件。**
    库跑在 WAL 模式下(见 db.get_conn),最近的写入可能还躺在 -wal 文件里、
    没合并进主库。直接拷 .db 会得到一份**缺了最新数据**的备份 ——
    而且它长得完全正常,等你真要恢复时才发现少了东西。
    第一次做备份就是这么错的:备份比真库整整小了 32KB。

    用 sqlite3 的 backup() 接口 —— 它知道 WAL 是怎么回事,
    而且允许库正在被写的时候安全地拷。

为什么这件事值得做:
    **这个库里没有一份数据是能重新生成的。**
    你的 star / 关注 / 表态 / 评论都在里面,快照尤其 ——
    它记录的是"某一天的 star 数",今天的机器算不出昨天的数字,
    丢了就是永久丢了。trending 的增速全靠它。

用法:
    .venv/bin/python backup_db.py              # 备份一份,保留最近 14 份
    .venv/bin/python backup_db.py --keep 30
    .venv/bin/python backup_db.py --list
"""
import glob
import os
import sqlite3
import sys
from datetime import datetime, timezone

import db

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "backups")
DEFAULT_KEEP = 14


def find_backups():
    return sorted(glob.glob(os.path.join(BACKUP_DIR, "repos-*.db")))


def list_backups():
    files = find_backups()
    if not files:
        print(f"还没有任何备份({BACKUP_DIR})")
        return
    print(f"{len(files)} 份备份,在 {BACKUP_DIR}:")
    for p in files:
        size = os.path.getsize(p) / 1024
        print(f"  {os.path.basename(p)}   {size:>8.0f} KB")


def backup(keep=DEFAULT_KEEP):
    if not os.path.exists(db.DB_PATH):
        print(f"还没有数据库:{db.DB_PATH}")
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"repos-{stamp}.db")

    src = sqlite3.connect(db.DB_PATH)
    out = sqlite3.connect(dest)
    try:
        src.backup(out)          # ← 关键:不是 shutil.copy / cp
    finally:
        out.close()
        src.close()

    # **验一下这个备份真的能用。**
    # "备份成功"和"备份可恢复"是两回事 —— 一个没验过的备份等于没有备份,
    # 因为你要到出事那天才会发现它是坏的,而那时已经晚了。
    try:
        check = sqlite3.connect(dest)
        verdict = check.execute("PRAGMA integrity_check").fetchone()[0]
        repos = check.execute("SELECT COUNT(*) FROM repos").fetchone()[0]
        snaps = check.execute("SELECT COUNT(*) FROM repo_snapshots").fetchone()[0]
        check.close()
    except Exception as e:                  # noqa: BLE001
        print(f"❌ 备份文件打不开:{type(e).__name__}: {e}")
        os.remove(dest)
        return None

    if verdict != "ok":
        print(f"❌ 备份完整性检查没过:{verdict}")
        os.remove(dest)
        return None

    size = os.path.getsize(dest) / 1024
    print(f"备份 → {os.path.basename(dest)}  ({size:.0f} KB,"
          f"完整性 ok,repos={repos} 快照={snaps})")

    # 只保留最近 keep 份。不清理的话,每天一份、一年 365 个文件,
    # 而它们每个都有几百 KB —— 磁盘不会立刻报警,但迟早要人手动收拾。
    for path in find_backups()[:-keep] if keep > 0 else []:
        os.remove(path)
        print(f"  删掉旧备份 {os.path.basename(path)}")
    print(f"现在共 {len(find_backups())} 份备份")
    return dest


def main():
    if "--list" in sys.argv:
        list_backups()
        return 0
    keep = DEFAULT_KEEP
    if "--keep" in sys.argv:
        try:
            keep = int(sys.argv[sys.argv.index("--keep") + 1])
        except (IndexError, ValueError):
            print("--keep 后面要跟一个数字,比如 --keep 30")
            return 2
    return 0 if backup(keep) else 1


if __name__ == "__main__":
    sys.exit(main())
