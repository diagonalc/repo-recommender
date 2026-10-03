#!/usr/bin/env python3
"""每天给**所有登录过的用户**同步 star 和关注。

为什么要单独有这个脚本(而不是在定时任务里直接调 sync_stars.py):
    sync_stars.py 一次只同步一个人(靠 REPOS_USER,默认 1 号)。
    站点对外开放之后用户会不止一个,而**用户是动态增加的** ——
    在定时任务里为每个人写一行命令不现实。
    所以这里负责"遍历所有人",sync_stars / sync_following 负责"同步一个人"。
    加新用户不用改任何配置。

为什么这件事重要:
    **推荐的口味信号就是 star。** 刚登录的人 star 还没同步的话,
    recommend.py 找不到任何正向信号,推荐页就是空的 ——
    用户看到的是"这个站坏了",而不是"再等一天就有数据了"。

失败隔离:
    **一个人失败不影响其他人。** 某人的 token 过期了,不该连带别人的数据
    也同步不上。所以每个人单独 try/except,最后汇总。

用法:
    .venv/bin/python sync_all.py
"""
import sys

import db
import sync_following
import sync_stars
from sync_common import SyncAuthError


def main():
    conn = db.get_conn()
    db.init_db(conn)

    users = db.users_with_token(conn)
    if not users:
        print("没有可同步的用户(还没人登录过,或者都没有 token)")
        return 0

    print(f"给 {len(users)} 个用户同步 star / 关注\n")
    ok_users, bad_users = [], []
    problems = []            # (login, label, 原因, "auth" 还是 "retry")

    for row in users:
        uid, login = row["id"], row["login"]
        print(f"--- {login} (id={uid}) ---")
        this_failed = False
        auth_failed = False
        for label, mod in (("star", sync_stars), ("关注", sync_following)):
            try:
                mod.sync_user(conn, uid)
            except SyncAuthError as e:
                # token 失效 —— 重试没有意义,要本人去重新登录
                this_failed = True
                auth_failed = True
                problems.append((login, label, str(e), "auth"))
                print(f"  [!] {label} 同步失败(要重新登录):{e}")
            except Exception as e:          # noqa: BLE001
                # 连非 RuntimeError 也接住:一个人身上出的任何意外,
                # 都不该让后面的人同步不上。宁可记下来继续跑。
                this_failed = True
                msg = str(e) if isinstance(e, RuntimeError) \
                    else f"{type(e).__name__}: {e}"
                problems.append((login, label, msg, "retry"))
                print(f"  [!] {label} 同步失败:{msg}")

        # 两个都跑完之后**收口**:只要其中任何一个报了 token 失效,最终就是失效。
        #
        # 不这么写会留一个很隐蔽的洞:star 同步失败(记 0)、关注同步却成功(记 1),
        # 最终状态成了"正常" —— 页面上不会出现提示,而 star 其实一直同步不上,
        # 又退回到那种"页面照常、数据悄悄不更新"的静默失败里去了。
        # 让状态反映**这一整轮的结果**,而不是"最后跑的那一个"。
        if auth_failed:
            db.set_token_status(conn, uid, False)

        (bad_users if this_failed else ok_users).append(login)
        print()

    # ---------------- 汇总 ----------------
    print("=" * 46)
    print(f"成功 {len(ok_users)} 人" + (f":{', '.join(ok_users)}" if ok_users else ""))
    if bad_users:
        print(f"失败 {len(bad_users)} 人:{', '.join(bad_users)}")
        for login, label, msg, kind in problems:
            mark = "要重新登录" if kind == "auth" else "可重试"
            print(f"    [{mark}] {login} / {label}:{msg}")
        if any(k == "auth" for *_, k in problems):
            print()
            print("提示:标着「要重新登录」的,让本人重新登录一次即可 ——")
            print("     GitHub 的 token 会失效,这不是程序故障,重试也不会好。")
    print("=" * 46)

    # ---------------- 退出码(给定时任务看)----------------
    #
    # 关键在于**区分"重试有用"和"重试没用"**:
    #
    #   全挂 + 有网络类失败  → 1,让任务重试(重试真的可能成功)
    #   全挂 + 全是 token 失效 → 0(重试一百次结果一样,只是白跑三轮)
    #   有人成功             → 0(个别人的问题不该让整轮重做)
    #
    # 不区分的话,一个过期的 token 会让任务每天空转三轮,
    # 日志里堆满一模一样的错误 —— 真正的问题反而被埋掉。
    retryable = any(k == "retry" for *_, k in problems)
    if bad_users and not ok_users and retryable:
        print("[停] 所有人都没同步成功,且失败看着是网络类 —— 让任务重试")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
