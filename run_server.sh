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

# ---------- 出网方式:直连,还是走代理 ----------
#
# **为什么必须在这儿写死**:进程的环境变量在**启动那一刻**就固定了 ——
# 你在外面把代理关掉,服务是不知道的。它会继续往那个已经不存在的端口发请求,
# 结果就是"登录卡住 → 502"。
#
# 这个坑特别隐蔽:**本机 /api/health 照常 200**,页面也照样打开,
# 只有**需要出网的功能全废** —— 登录、点 star、全站搜索、抓 README、头像代理、翻译。
# 看起来像"某个功能坏了",实际是"整条出网链路断了"。
#
# 想走代理就传:REPOS_HTTP_PROXY=http://127.0.0.1:7897 ./run_server.sh
# 不传 = 直连(当前 GitHub 从这台机器直连只要 0.1~0.2 秒,够用)。
HTTP_PROXY_CFG="${REPOS_HTTP_PROXY:-}"
if [ -n "$HTTP_PROXY_CFG" ]; then
  export http_proxy="$HTTP_PROXY_CFG" https_proxy="$HTTP_PROXY_CFG"
  export HTTP_PROXY="$HTTP_PROXY_CFG" HTTPS_PROXY="$HTTP_PROXY_CFG"
else
  # 显式清掉 —— 别让 shell 里飘着的代理变量偷偷影响这个服务
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
fi

cd /home/diagonalc/repo-recommender || exit 1
mkdir -p logs

echo "本机访问:  http://127.0.0.1:$PORT/"
if [ -n "$REPOS_PUBLIC_BASE" ]; then
  echo "公开地址:  $REPOS_PUBLIC_BASE/"
else
  echo "公开地址:  (未设置 —— 本地模式)"
fi
# 把出网方式也打出来 —— 登录 / 搜索 / 抓 README 全靠它,出问题第一个要看这里
if [ -n "$HTTP_PROXY_CFG" ]; then
  echo "出网方式:  走代理 $HTTP_PROXY_CFG"
else
  echo "出网方式:  直连"
fi

# --proxy-headers       让 uvicorn 相信反向代理给的 X-Forwarded-* 头
# --forwarded-allow-ips 但只信任来自本机的转发(隧道就是从本机连进来的),
#                       不信任外来的头 —— 否则别人可以伪造 IP 和协议
exec .venv/bin/uvicorn api:app --host 0.0.0.0 --port "$PORT" \
     --proxy-headers --forwarded-allow-ips "127.0.0.1"

     
