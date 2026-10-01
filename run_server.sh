#!/bin/bash
# 启动服务。端口和公开地址都只在这里写一次 ——
# 改端口就改这一行,别让它散落在 README、crontab、各种笔记里(那种迟早对不上)。

PORT=18080

# 公开访问地址。**线上必填,本地留空。**
#
#   本地:  留空 → 代码从请求里推地址(127.0.0.1 也对得上)
#   线上:  填用户实际打开的地址,例如
#             REPOS_PUBLIC_BASE=https://diagonalc.dpdns.org ./run_server.sh
#
# 为什么线上必须写死:走隧道 / 反向代理时,Cloudflare 在边缘就终止了 HTTPS,
# 转发给本地的是**明文 http**。从请求里推会算出 http://...,而用户看到的是
# https://...,GitHub 会以 redirect_uri mismatch 拒绝登录。
#
# ⚠️ 这个值必须和 GitHub OAuth App 里登记的回调地址前缀**完全一致**。
REPOS_PUBLIC_BASE="${REPOS_PUBLIC_BASE:-}"
export REPOS_PUBLIC_BASE

cd /home/diagonalc/repo-recommender || exit 1
mkdir -p logs

echo "本机访问:  http://127.0.0.1:$PORT/"
if [ -n "$REPOS_PUBLIC_BASE" ]; then
  echo "公开地址:  $REPOS_PUBLIC_BASE/"
else
  echo "公开地址:  (未设置 —— 本地模式)"
fi

# --proxy-headers       让 uvicorn 相信反向代理给的 X-Forwarded-* 头
# --forwarded-allow-ips 但只信任来自本机的转发(隧道就是从本机连进来的),
#                       不信任外来的头 —— 否则别人可以伪造 IP 和协议
exec .venv/bin/uvicorn api:app --host 0.0.0.0 --port "$PORT" \
     --proxy-headers --forwarded-allow-ips "127.0.0.1"
