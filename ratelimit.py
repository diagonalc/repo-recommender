#!/usr/bin/env python3
"""按 IP 限流。

**为什么需要它**(不是"防黑客"那种理由):
    全站搜索和抓 README 用的是**共享的** GitHub token —— 认证后搜索接口
    只有 30 次/分钟。一个人连点几下就能把额度打光,其他人跟着一起搜不了,
    而他们完全不知道发生了什么,只会觉得"这站坏了"。
    翻译接口同理:MyMemory 匿名额度是按 IP 算的。

所以这里限制的是"**一个人把公共资源用光**",不是"挡住攻击者"。
阈值故意定得很宽 —— 正常人手点根本碰不到,它拦的是手滑和脚本。

为什么放内存里、不用 Redis:
    单进程、单机、个位数用户。一个 dict 就够了。
    **重启会清零** —— 对这个场景无所谓(没人会靠重启服务来绕过限流)。
    真要上多进程了再换,那时候这个文件就是唯一要改的地方。
"""
import time
from collections import deque

# {key: deque[打点时间]};deque 里只保留窗口内的记录
_hits = {}
_last_cleanup = 0.0
CLEANUP_EVERY = 300.0      # 每 5 分钟扫一次,把空掉的 key 删掉


def _cleanup(now):
    """把已经没有记录的 key 删掉。

    不做的话,每个来过的 IP 都会在字典里留一个空 deque ——
    对公网服务来说这就是个慢性内存泄漏,而且看不出来。
    """
    global _last_cleanup
    if now - _last_cleanup < CLEANUP_EVERY:
        return
    _last_cleanup = now
    dead = [k for k, dq in _hits.items() if not dq]
    for k in dead:
        del _hits[k]


def allow(key, limit, window=60.0):
    """记一次打点。超了就返回 False。

    固定窗口:保留 window 秒内的打点,数量达到 limit 就拒绝。
    (比"令牌桶"粗,但足够用,而且一眼能看懂 —— 这个项目的原则。)
    """
    now = time.time()
    _cleanup(now)

    dq = _hits.get(key)
    if dq is None:
        dq = _hits[key] = deque()
    cutoff = now - window
    while dq and dq[0] <= cutoff:
        dq.popleft()
    if len(dq) >= limit:
        return False
    dq.append(now)
    return True


def client_ip(request):
    """拿请求方 IP。

    走隧道时,uvicorn 的 --proxy-headers 会把 X-Forwarded-For 解析好写进
    request.client —— 前提是它信任那个转发来源(run_server.sh 里限定了
    只信任 127.0.0.1,也就是只信任本机的 cloudflared)。
    所以这里拿到的就是**用户真实 IP**,不是 Cloudflare 的。

    拿不到就退回 "?" —— 所有人共用一个额度。宁可限得紧一点,
    也不要因为拿不到 IP 就完全不限。
    """
    return getattr(getattr(request, "client", None), "host", None) or "?"
