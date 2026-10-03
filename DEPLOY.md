# 部署与运维 / DEPLOY

> 项目现在跑在**一台家用笔记本的 WSL 里**,通过 Cloudflare 隧道对公网开放。
> 这份文档记的是"怎么启、怎么停、出问题看哪里",以及**为什么当初这么配**。
>
> 代码相关看 [README.md](README.md),架构看 [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md),
> 踩坑的来龙去脉看 [DEVLOG.md](DEVLOG.md)。

---

## 一、现在的样子

```
   用户浏览器
        │  https://diagonalc.dpdns.org
        ▼
   Cloudflare 边缘 ──── 隧道(出站连接,不用开任何入站端口)
        │
        ▼
   cloudflared(跑在 WSL 里,常驻)
        │  http://localhost:18080
        ▼
   uvicorn(跑在 WSL 里,常驻)
        │
        ▼
   data/repos.db(SQLite,单文件)
```

**关键点:整条链路上没有一个"对公网开放的入站端口"。**
cloudflared 是**主动连出去**到 Cloudflare 的,所以家里不需要公网 IP、
不需要端口映射、路由器也不用动。这也是为什么它比"买台 VPS"更适合这个场景。

| 组件 | 在哪 | 怎么起来 |
|---|---|---|
| `cloudflared` | WSL | 手动/开机自启(见下) |
| `uvicorn` | WSL | `run_server.sh` |
| 每日采集 | Windows 任务计划 | `RepoRecommenderDaily` |

---

## 二、起服务

### 网站服务

```bash
cd ~/repo-recommender
REPOS_PUBLIC_BASE=https://diagonalc.dpdns.org bash run_server.sh
```

**`REPOS_PUBLIC_BASE` 线上必填,不填登录会坏。** 原因:Cloudflare 在边缘就终止了 HTTPS,
转发给本地的是**明文 http**,于是代码从请求里推出来的地址是 `http://...`,
而用户看到的是 `https://...`,两者对不上,GitHub 会以 `redirect_uri mismatch` 拒绝登录。

> 这个值必须和 GitHub OAuth App 里登记的回调地址**前缀完全一致**。

想让它**脱离终端常驻**(关掉这个终端也不死):

```bash
REPOS_PUBLIC_BASE=https://diagonalc.dpdns.org \
  setsid nohup bash run_server.sh >> logs/server.out 2>&1 < /dev/null &
```

`setsid` 让它成为独立的会话首进程 —— 不会被"启动它的那个终端"一起带走。

### 隧道

```bash
cd ~/repo-recommender
nohup ./cloudflared tunnel run repos >> logs/tunnel.log 2>&1 &
```

配置在 `~/.cloudflared/config.yml`:

```yaml
tunnel: repos
credentials-file: /home/diagonalc/.cloudflared/99725a0b-7397-4c57-ad69-014b8acfe398.json
ingress:
  - hostname: diagonalc.dpdns.org
    service: http://localhost:18080
  - service: http_status:404
```

**隧道 ID `99725a0b-7397-4c57-ad69-014b8acfe398` 要留着** ——
重装/换机器时,把它和 `config.yml` 一起搬过去就能接上同一个域名。

### 日常速查

```bash
# 服务活着吗?(200 = 活着)
curl -s -o /dev/null -w "%{http_code}\n" --noproxy '*' http://127.0.0.1:18080/api/me

# ★ 最该常看的一条:服务活着 + 数据新不新鲜
#   stale_days 正常 ≤1;连着变大就是每日任务挂了,而页面完全看不出来
curl -s --noproxy '*' http://127.0.0.1:18080/api/health

# 公网通不通?
curl -s -o /dev/null -w "%{http_code}\n" https://diagonalc.dpdns.org/

# 谁在跑?
pgrep -af 'uvicorn api:app'
pgrep -af cloudflared

# 重启网站服务(注意下面这个方括号!)
pkill -f '[u]vicorn api:app'
REPOS_PUBLIC_BASE=https://diagonalc.dpdns.org \
  setsid nohup bash run_server.sh >> logs/server.out 2>&1 < /dev/null &

# 日志
tail -f logs/server.out
tail -f logs/daily.log
```

> ⚠️ `pkill -f "uvicorn api:app"` 会**把执行这条命令的 shell 自己也匹配上**并杀掉
> (因为它的命令行里就含这个字符串)。写成 `pkill -f '[u]vicorn api:app'`,
> 方括号让模式匹配不到自己。

---

## 三、局域网访问(WSL + Windows 特有的四层坑)

如果只想让**同一个 WiFi 下的手机**能打开,不需要隧道,但下面四样缺一个都不通。
这几样都**不在仓库里**(在 Windows 侧),所以单独记。

### ① WSL 要开镜像网络

`C:\Users\Lenovo\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
```

默认的 NAT 模式给 WSL 分配一个内网 IP(`172.19.x.x`),**局域网设备访问不到它**。
镜像模式让 WSL 直接共享 Windows 的网卡。**改完必须 `wsl --shutdown` 才生效。**

### ② Windows 防火墙要放行

```
netsh advfirewall firewall add rule name="Repos18080" dir=in action=allow protocol=TCP localport=18080 remoteip=localsubnet
```

`remoteip=localsubnet` 是**特意加的**:这台机器在校园网里,不加这个参数等于
**对整个校园网开放端口**。

### ③ 还有第二层防火墙

Win11 的 **Hyper-V Firewall** 是 WSL 专用的,入站默认 **Block**,和 Windows 防火墙是两回事:

```
New-NetFirewallHyperVRule -Name "Repos18080" -DisplayName "Repos 18080" -Direction Inbound -VMCreatorId "{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}" -Protocol TCP -LocalPorts 18080 -Action Allow
```

那个 GUID 是本机 WSL 的标识,用 `Get-NetFirewallHyperVVMSetting -PolicyStore ActiveStore` 查。

### ④ 本机访问自己有个"捷径"(未解决,但不影响别人)

Windows 访问**自己的局域网 IP / 主机名**时,内核会抄近路,翻的是自己的 socket 表,
所以**本机连不上,只能用 `127.0.0.1`**;而**别的设备完全正常**。

> **踩过的坑:"从 Windows 访问 Windows 自己的局域网 IP"是个不可靠的测试。**
> 这条路径不通,但局域网设备访问完全正常 —— 因为这个假信号白折腾了很久。
> **要验证局域网可达性,就该用另一台设备测。**

**上了公网之后这四层全部消失** —— 因为走的是隧道,域名也固定了。

---

## 四、定时采集任务

### 它做什么

```
Windows 任务计划(每天 10:17 和 18:17)
   → C:\Users\Lenovo\repo-recommender-daily.bat
   → wsl.exe 启动 WSL
   → run_daily.sh(带 flock 锁)
   → daily_update.py
   → 拉 12 页(6 种语言 × 2 页)→ 刷新 repos 表 + 记当天的 star 快照
```

### 任务定义

`RepoRecommenderDaily.xml` 是**唯一真源**。改运行时间/电源策略就改这个文件,然后重新导入:

```
schtasks /create /tn RepoRecommenderDaily /xml RepoRecommenderDaily.xml /f
```

**不要在"任务计划程序"GUI 里改** —— GUI 改完和文件就对不上了,下次一导入就被覆盖。

> ⚠️ 导入有两个坑:
> 1. 文件必须是 **UTF-16LE 带 BOM**。仓库里存的就是这个编码,别让编辑器"顺手"转成 UTF-8,
>    那会报"XML 格式不正确"。转换:`printf '\xff\xfe' > out.xml && iconv -f UTF-8 -t UTF-16LE in.xml >> out.xml`
> 2. **XML 注释里不能出现连续两个减号。** 写 `wsl.exe ... -- bash` 会报
>    "不正确的备注语法"。

### 为什么是这么配的(2026-10-02 修过)

原来的配置**连续丢了两天数据**(09-29 和 10-01),三个原因叠在一起:

| 问题 | 原来的值 | 现在 |
|---|---|---|
| 笔记本一拔电源就不跑 | `在电池模式停止 / 不用电池启动` | **插不插电都跑** |
| 错过了不补 | `StartWhenAvailable` 关闭 | **打开**(机器恢复后补跑) |
| 崩了不重试 | 无 | **10 分钟 × 3 次** |
| 单次超时过长(会和第二天重叠) | 72 小时 | **2 小时** |
| 一天只触发一次 | 10:17 | **10:17 + 18:17** |

> 跑两次**不会产生重复数据**:快照表主键是 `(repo_id, snapshot_date)`,
> 同一天写第二遍是覆盖。

**已知限制**:任务的登录类型是 `InteractiveToken`,即**要求用户处于登录状态**。
锁屏算登录(仍会跑),**注销了就不会跑**。改成"不管用户是否登录"需要存 Windows 密码,
对 WSL 任务来说风险更大,暂不改。

### 脚本侧的三道保险

1. `daily_update.py` **一个 repo 都没拉到就非零退出** —— 否则会写 0 行快照然后 exit 0,
   任务看到"成功"就不重试,这天就**静默地**丢了。
2. `fetch_repos.py` 把网络错误退避重试后转成 `RuntimeError`,**只跳过一个语言,不炸整个 job**。
3. `run_daily.sh` 用 `flock` 保证**同一时刻只有一个实例**(两次触发不撞车,
   也避免两个进程同时写 SQLite 撞 `database is locked`)。

---

## 五、凭据

两个文件,都在 `~/.config/repo-recommender/`,**都在仓库之外**:

| 文件 | 内容 | 用途 |
|---|---|---|
| `token` | GitHub Personal Access Token | 采集数据(不带会被限流到 10 次/分钟) |
| `oauth.env` | `REPOS_GH_CLIENT_ID` / `REPOS_GH_CLIENT_SECRET` | 登录 |

```bash
chmod 600 ~/.config/repo-recommender/token
chmod 600 ~/.config/repo-recommender/oauth.env
```

> ⚠️ **永远不要把 token / client secret 粘进聊天、写进会被提交的文件、或放进命令历史。**
> 一旦推到 GitHub,几分钟内就会被爬虫拿到并滥用。
> 如果真的粘进了终端,立刻去 GitHub 设置里撤销重发。

---

## 六、代理

WSL 里有一组代理环境变量,指向 Windows 侧跑着的 mihomo(`127.0.0.1:7897`):

```
http_proxy=http://127.0.0.1:7897
https_proxy=http://127.0.0.1:7897
no_proxy=172.31.*,172.30.*,...,10.*,192.168.*,127.*,localhost
```

**访问 GitHub 走的是这个代理**(直连不稳定)。由此带来两个必须知道的后果:

**① 代理抖动会直接打断采集任务。**
2026-10-02 那天的采集就是被这个搞崩的:

```
requests.exceptions.SSLError: ... SSL: UNEXPECTED_EOF_WHILE_READING
```

代理在传输中途断开了连接。现在 `fetch_repos.py` 会把这类错误退避重试 4 次,
仍不行就只跳过一个语言、不炸整个 job。**但根因还在代理** ——
如果发现日志里这类错误变多,先去看看 mihomo 是不是不稳。

**② 在 WSL 里 `curl 127.0.0.1:18080` 会走代理,可能拿到一个假的 502。**
那**不是服务挂了**,是代理接不住本地请求。测本机服务要加 `--noproxy '*'`:

```bash
curl -s -o /dev/null -w "%{http_code}\n" --noproxy '*' http://127.0.0.1:18080/api/me
```

**③ OAuth 换 token 也走代理。** 所以 `auth.py` 里对 `requests` 的异常专门报
"连不上 GitHub 换取 token…检查代理是否正常",而不是丢一个 500 出来。

---

## 七、改完前端看不到新版本?(缓存这一层)

**症状**:接口明明更新了,页面纹丝不动。而且服务端这边怎么看都是对的 ——
本地和公网拉的 `app.js` 哈希一致、`curl` 也正常。

**根因**:**Cloudflare 会强行改写 `.js` / `.css` 的缓存头。**

| 源站发的 | Cloudflare 回给浏览器的 |
|---|---|
| `Cache-Control: no-cache` | `max-age=14400`(4 小时) |
| `no-cache, max-age=0, must-revalidate` | **`max-age=14400, must-revalidate`** |

**对静态扩展名,源站说了不算** —— 它会套上自己的 Browser Cache TTL 默认值。
(想改的话在 Cloudflare 面板:缓存 → 配置 → Browser Cache TTL → 改成
"Respect Existing Headers"。但下面这个做法不需要动面板。)

**已经修好的做法:版本号绑到文件内容上。**

```
index.html 里写  <script src="app.js?v=__ASSET_V__"></script>
api.py 运行时    __ASSET_V__ → app.js 的 sha256 前 10 位
```

内容变了 URL 就变,浏览器必定重新下载;内容没变就走缓存。
**所以改前端不用再手动改任何版本号** —— 它现在是自动的。

> HTML 不在这套缓存规则里(实测 `cf-cache-status: DYNAMIC`,不缓存),
> 所以版本号注入在 HTML 里是有效的。这也是为什么首页要由代码渲染
> (`api.py` 的 `index_page()`)、而不是交给 StaticFiles —— 见
> [DEVLOG.md](DEVLOG.md) 的"第九阶段"。

**如果还是看到旧版本**:

1. 先试普通刷新(F5)
2. 不行就强制刷新:`Ctrl+Shift+R`(Mac 是 `Cmd+Shift+R`)
3. 手机上可能要在浏览器设置里清一次站点数据

---

## 八、还没做的

1. **开机自启** —— 现在 uvicorn 和 cloudflared 都要手动拉起。电脑重启后网站就是断的。
   要做到自启有两条路:Windows 任务计划(登录时触发),或者在 WSL 里配 systemd 服务。
2. **HTTPS 之外的加固** —— 会话 cookie 还没加 `Secure` 标志,速率限制也没有。
   当前是"给朋友用"的强度,不是"对陌生人开放"的强度。
3. **数据库备份** —— 现在没有自动备份。
   ⚠️ 真要做的话记住:**WAL 模式的数据库不能直接 `cp` 那个 `.db` 文件**,
   要连 `-wal` 一起,或者用 `sqlite3` 的 `backup()` 接口(直接拷会漏掉最近的数据)。
