// P8:前端逻辑。原生 JS,没有框架。
//
// 路由:用 hash(#/xxx)把"在看哪一页"放进 URL。
//   为什么用 hash 不用路径:静态服务器直接能用,刷新不会 404,不需要后端配合。
//   好处是**浏览器的前进/后退真的能用**,而不是只能点页面里那个"返回"。
//
// 导航:左侧竖栏(悬停展开)+ 中间窄栏内容。文案统一走 t("key"),中英可切;外观中英同理。
// 前后端现在是**同一个端口**(FastAPI 直接托管前端),所以用相对路径就行。
// 只有开发时前端单独跑在 5500 上,才需要指回 8000。
const API = location.port === "5500" ? `http://${location.hostname}:8000` : "";

// 所有请求都带上 cookie —— 会话就靠它。
// (同源时浏览器默认会带,但显式写出来,换端口开发时也不会忘)
const FETCH_OPTS = { credentials: "include" };

const I18N = {
  zh: {
    tab_trending: "Trending", tab_recommend: "为你推荐", tab_tags: "标签",
    tab_starred: "已收藏", tab_search: "搜索", tab_following: "已关注",
    tab_acg: "兔子洞",
    acg_back: "返回主站",
    acg_tags: "标签",
    acg_search: "在兔子洞里搜",
    acg_summary: "共 {0} 个 · 下滑显示更多",
    acg_no_match: "兔子洞里没搜到匹配的。",
    acg_tag_title: "共 {0} 个标签 · 点一个看带它的仓库",
    starred_view_list: "列表",
    starred_view_status: "现状",
    status_sort_growth: "最近涨得最快",
    status_sort_stale: "最久没更新",
    status_sort_recent: "最近 star 的",
    status_sort_stars: "星数最多",
    status_summary: "{0} 个 · 还在更新 {1} · 放缓 {2} · 停更 {3}",
    health_active: "还在更新", health_slowing: "放缓", health_stale: "停更",
    health_unknown: "不清楚",
    days_ago: "{0} 天前", days_today: "今天动过",
    status_delta_none: "不在快照池里",
    status_note: "「+N」是最近一次快照(两天)的增量。我们并不知道你 star 它时有多少星 —— 快照是后来才开始记的,所以算不出「从你 star 到现在涨了多少」。",
    summary_following: "你关注的 {0} 个开发者",
    following_empty: "还没有关注数据 —— 跑一次 sync_following.py 就有了。",
    follow_no_match: "没找到匹配的人。",
    follow_search: "搜索已关注的人",
    follow_sort_name: "名字",
    follow_sort_recent: "关注时间(新→旧)",
    follow_sort_oldest: "关注时间(旧→新)",
    translate: "翻译成当前语言",
    translate_fail: "翻译失败:",
    theme_light: "白天模式", theme_dark: "夜晚模式",
    lang_zh: "中文", lang_en: "English",
    sort_trending: "最近增量", sort_stars: "总星数", sort_pushed: "最近更新", sort_name: "名称",
    sort_similarity: "相似度", sort_relevance: "相关度", sort_added: "最近收录",
    refresh: "刷新",
    loading: "加载中…", no_data: "没有数据。", error: "出错了:",
    open_github: "在 GitHub 打开", releases: "Releases", back: "返回上一页",
    interested: "感兴趣", not_interested: "不感兴趣", fail: "失败:",
    more: "更多", menu: "导航", copy_link: "复制链接", copied: "已复制链接",
    un_not_interested: "取消不感兴趣",
    comments_go: "查看评论", star_go: "在 GitHub 上 star", starred_ok: "已 star ✓",
    me: "我",
    login: "用 GitHub 登录",
    logout: "退出登录",
    token_bad: "你的 GitHub 授权已失效,新的 star 不再同步进来了。重新登录一次就能恢复 —— 已有的数据都还在。",
    token_bad_go: "重新登录",
    login_blurb: "记录你的 star、关注和口味,每天给你推对口味的 repo。",
    login_not_ready: "还没配置 OAuth 凭据:把 Client ID / Secret 填进 ~/.config/repo-recommender/oauth.env",
    snapshots: "star 快照 ({0})", readme: "README",
    readme_none: "还没抓到这个 repo 的 README。",
    similar: "相似的 repo", similarity: "相似度",
    comments: "评论 ({0})", comment_placeholder: "写下你的评论…",
    comment_send: "发表", comment_none: "还没有评论。", comment_fail: "发表失败:",
    tag_remove: "点一下移除", tag_add: "点一下筛选",
    tag_empty: "没有同时带这些标签的 repo —— 点掉上面一个试试。",
    tagcloud_title: "{0} 个标签 · 覆盖 {1}/{2} 个 repo",
    tag_search: "搜索标签",
    tag_search_hit: "匹配「{0}」的标签 · {1} 个",
    tag_no_match: "没有匹配的标签。",
    summary_trending: "近两个快照日({0} → {1})增量 Top {2}",
    summary_sorted: "按{0} · {1} 个",
    summary_tags: "{1} 个(标签 {0} · 按{2})",
    summary_recommend: "已加载 {0} 个 · 继续下滑看更多",
    list_end: "— 到底了 —",
    summary_starred: "{0} 个(按 star 时间倒序)",
    summary_search: "「{0}」· {1} 个",
    search_empty: "没搜到匹配的 repo。",
    search_placeholder: "搜索 repo:名字 / 描述 / 标签 / README",
    search_go: "搜索",
    scope_local: "本地库", scope_github: "全 GitHub",
    summary_search_github: "GitHub 全站「{0}」· {1} 个",
    discover_tags: "热门标签",
    discover_trending: "上升最快",
    discover_authors: "你 star 过的作者",
    discover_empty: "还没有数据,先去 Trending 看看。",
    detail_error: "打不开详情:", starred_at: "star 于", last_push: "最后推送",
    delta_recent: "最近快照 ▲",
    because_starred: "因为你 star 过 ", because_liked: "因为你点过感兴趣 ",
    reason_explore: "换换口味",
    reason_explore_plain: "换换口味:它不像你以前 star 过的东西,但很多人在用。留几个这样的位置,是为了让你别只看得到同一类仓库。",
    reason_explore_growth: "换换口味:它不像你以前 star 过的东西,最近两天还涨了 {0} 颗星。",
  },
  en: {
    tab_trending: "Trending", tab_recommend: "For You", tab_tags: "Tags",
    tab_starred: "Starred", tab_search: "Search", tab_following: "Following",
    tab_acg: "Rabbit hole",
    acg_back: "Back to main site",
    acg_tags: "Tags",
    acg_search: "Search the rabbit hole",
    acg_summary: "{0} repos · scroll for more",
    acg_no_match: "Nothing matched in the rabbit hole.",
    acg_tag_title: "{0} tags · click one to see its repos",
    starred_view_list: "List",
    starred_view_status: "Status",
    status_sort_growth: "Growing fastest",
    status_sort_stale: "Least recently updated",
    status_sort_recent: "Recently starred",
    status_sort_stars: "Most stars",
    status_summary: "{0} repos · {1} active · {2} slowing · {3} stale",
    health_active: "Active", health_slowing: "Slowing", health_stale: "Stale",
    health_unknown: "Unknown",
    days_ago: "{0} days ago", days_today: "Updated today",
    status_delta_none: "not in snapshot pool",
    status_note: "“+N” is growth over the latest snapshot (~2 days). We do NOT know how many stars it had when you starred it — snapshots started later.",
    summary_following: "{0} developers you follow",
    following_empty: "No following data yet — run sync_following.py once.",
    follow_no_match: "No matching people.",
    follow_search: "Search people you follow",
    follow_sort_name: "Name",
    follow_sort_recent: "Followed (newest)",
    follow_sort_oldest: "Followed (oldest)",
    translate: "Translate to current language",
    translate_fail: "Translate failed: ",
    theme_light: "Light mode", theme_dark: "Dark mode",
    lang_zh: "中文", lang_en: "English",
    sort_trending: "Recent growth", sort_stars: "Total stars",
    sort_pushed: "Recently updated", sort_name: "Name", sort_similarity: "Similarity",
    sort_relevance: "Relevance", sort_added: "Recently added",
    refresh: "Refresh",
    loading: "Loading…", no_data: "No data.", error: "Error:",
    open_github: "Open on GitHub", releases: "Releases", back: "Go back",
    interested: "Interested", not_interested: "Not interested", fail: "Failed: ",
    more: "More", menu: "Menu", copy_link: "Copy link", copied: "Link copied",
    un_not_interested: "Undo not interested",
    comments_go: "View comments", star_go: "Star on GitHub", starred_ok: "Starred ✓",
    me: "me",
    login: "Sign in with GitHub",
    logout: "Sign out",
    token_bad: "Your GitHub authorization has expired, so new stars are no longer syncing. Sign in again to fix it — nothing already saved is lost.",
    token_bad_go: "Sign in again",
    login_blurb: "Tracks your stars and interests, and recommends repos you'll actually like.",
    login_not_ready: "OAuth credentials not configured: fill Client ID / Secret into oauth.env",
    snapshots: "Star snapshots ({0})", readme: "README",
    readme_none: "No README captured yet.",
    similar: "Similar repos", similarity: "similarity",
    comments: "Comments ({0})", comment_placeholder: "Write a comment…",
    comment_send: "Post", comment_none: "No comments yet.", comment_fail: "Failed: ",
    tag_remove: "Click to remove", tag_add: "Click to filter",
    tag_empty: "No repo has all of these tags — click one above to remove it.",
    tagcloud_title: "{0} tags · {1}/{2} repos",
    tag_search: "Search tags",
    tag_search_hit: "Tags matching “{0}” · {1}",
    tag_no_match: "No tags matched.",
    summary_trending: "Top {2} by growth ({0} → {1})",
    summary_sorted: "{0} · {1} repos",
    summary_tags: "{1} repos (tags {0} · {2})",
    summary_recommend: "{0} loaded · scroll for more",
    list_end: "— that's all —",
    summary_starred: "{0} repos (newest first)",
    summary_search: "“{0}” · {1} repos",
    search_empty: "No repos matched.",
    search_placeholder: "Search repos: name / description / tag / README",
    search_go: "Search",
    scope_local: "Local", scope_github: "All GitHub",
    summary_search_github: "GitHub: “{0}” · {1} repos",
    discover_tags: "Popular tags",
    discover_trending: "Trending up",
    discover_authors: "Authors you starred",
    discover_empty: "Nothing here yet — check Trending first.",
    detail_error: "Cannot open detail: ", starred_at: "starred", last_push: "last push",
    delta_recent: "since last snapshot ▲",
    because_starred: "because you starred ", because_liked: "because you liked ",
    reason_explore: "Something different",
    reason_explore_plain: "Something different: not like what you've starred, but a lot of people use it. A few slots like this keep you from seeing only one kind of repo.",
    reason_explore_growth: "Something different: not like what you've starred, and it gained {0} stars in the last two days.",
  },
};

let lang = localStorage.getItem("ui_lang") || "zh";

function t(key, ...args) {
  const table = I18N[lang] || I18N.zh;
  let s = table[key] !== undefined ? table[key] : (I18N.zh[key] || key);
  args.forEach((a, i) => { s = s.replace("{" + i + "}", a); });
  return s;
}

// 外观:夜晚(默认)/ 白天。存 localStorage;没存过就跟随系统偏好。
function currentTheme() {
  const saved = localStorage.getItem("theme");
  if (saved) return saved;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}
function applyTheme(theme) {
  document.body.classList.toggle("light", theme === "light");
}

// 窗口铺满屏幕(浏览器最大化 / 全屏)时,导航直接摊开;不满屏才收成图标。
// 判断方式:窗口宽度离屏幕可用宽度只剩一点点,就说明是铺满状态。
function syncRailOpen() {
  const avail = screen.availWidth || window.innerWidth;
  // ⚠️ 必须加宽度门槛:手机上 window.innerWidth 几乎等于屏幕宽度,
  // 只看"离屏幕宽只差一点点"的话,手机永远判定成"全屏",导航会一直撑着不收回。
  // 大屏幕(≥1000px)才认为是"窗口铺满",这时才自动展开。
  const wide = window.innerWidth >= 1000;
  document.body.classList.toggle("rail-open", wide && window.innerWidth >= avail - 8);
}

// 线条图标,风格对齐 Threads / X(细描边、圆角端点)。自己画的,不是扒来的素材。
const ICONS = {
  trending:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linecap="round" stroke-linejoin="round">' +
    '<polyline points="3 17 9 11 13 15 21 7"/><polyline points="15 7 21 7 21 13"/></svg>',
  spark:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linejoin="round">' +
    '<path d="M11 3l1.7 4.8L17.5 9.5l-4.8 1.7L11 16l-1.7-4.8L4.5 9.5l4.8-1.7z"/>' +
    '<path d="M18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/></svg>',
  tag:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linejoin="round">' +
    '<path d="M20.6 13.4l-7.2 7.2a2 2 0 01-2.8 0L2 12V2h10l8.6 8.6a2 2 0 010 2.8z"/>' +
    '<circle cx="7" cy="7" r="1.3" fill="currentColor" stroke="none"/></svg>',
  star:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linejoin="round">' +
    '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8L3.5 9.7l5.9-.9z"/></svg>',
  search:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linecap="round">' +
    '<circle cx="10.5" cy="10.5" r="6.5"/><line x1="15.6" y1="15.6" x2="21" y2="21"/></svg>',
  refresh:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M20 12a8 8 0 11-2.3-5.7"/><polyline points="20 4 20 10 14 10"/></svg>',
  globe:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/>' +
    '<path d="M12 3c2.5 2.5 3.8 5.6 3.8 9S14.5 18.5 12 21c-2.5-2.5-3.8-5.6-3.8-9S9.5 5.5 12 3z"/></svg>',
  sun:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/>' +
    '<path d="M12 2v2.4M12 19.6V22M2 12h2.4M19.6 12H22' +
    'M4.9 4.9l1.7 1.7M17.4 17.4l1.7 1.7M19.1 4.9l-1.7 1.7M6.6 17.4l-1.7 1.7"/></svg>',
  moon:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linejoin="round"><path d="M20.5 14.6A8.6 8.6 0 019.4 3.5a8.6 8.6 0 1011.1 11.1z"/></svg>',
  // 站标:天文台(圆顶 + 观测缝 + 地平线)。
  // 之前是"方框里三条越来越短的横线"(一列条目 = 推荐流的形状),
  // 换成这个是因为站名叫 Observatory —— 图标和名字对不上就别扭。
  // 站标:天文台 —— 圆顶 + 从观测缝里伸出来的望远镜。
  //
  // 上一版只有"圆顶 + 一条竖线",渲染出来像**一口钟**。加了伸出来的镜筒之后
  // 才一眼能认出是天文台(镜筒是斜的,而且顶端有个垂直的镜口)。
  // ⚠️ 别删那截镜口 —— 只有一根斜线的话,看着像天线或者天线杆。
  brand:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M2.8 20.6h18.4"/>' +
    '<path d="M5.4 20.6a6.6 6.6 0 0 1 13.2 0"/>' +
    '<path d="M12.4 13.9 18.6 7.7"/>' +
    '<path d="M17.3 6.4 19.9 9"/></svg>',
  // (这里原来有个叫 anime 的线条图标,想画一个少女。
  //  渲染出来依次像幽灵 / 外星人 / 披斗篷的人 / 熊脸 —— 四版都不行,
  //  最后改用用户给的图片了,理由见 railButton 里那段注释。)
  //
  // 心:空心/实心两版。感兴趣的状态靠"变实心 + 变色"表达,不写文字。
  heart:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linejoin="round">' +
    '<path d="M12 20.5C6.5 16 3 13 3 9.2A4.7 4.7 0 017.7 4.5c1.7 0 3.2.9 4.3 2.5 ' +
    '1.1-1.6 2.6-2.5 4.3-2.5A4.7 4.7 0 0121 9.2c0 3.8-3.5 6.8-9 11.3z"/></svg>',
  heartFilled:
    '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none">' +
    '<path d="M12 20.5C6.5 16 3 13 3 9.2A4.7 4.7 0 017.7 4.5c1.7 0 3.2.9 4.3 2.5 ' +
    '1.1-1.6 2.6-2.5 4.3-2.5A4.7 4.7 0 0121 9.2c0 3.8-3.5 6.8-9 11.3z"/></svg>',
  comment:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linejoin="round">' +
    '<path d="M21 11.7c0 4.1-4 7.4-9 7.4-1 0-2-.1-2.9-.4L4.5 20.6l1.2-3.5' +
    'A7.1 7.1 0 013 11.7c0-4.1 4-7.4 9-7.4s9 3.3 9 7.4z"/></svg>',
  more:
    '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none">' +
    '<circle cx="5" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/>' +
    '<circle cx="19" cy="12" r="1.8"/></svg>',
  copy:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linejoin="round">' +
    '<rect x="9" y="9" width="12" height="12" rx="3"/>' +
    '<path d="M6 15H5a2 2 0 01-2-2V5a2 2 0 012-2h8a2 2 0 012 2v1"/></svg>',
  ban:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linecap="round"><circle cx="12" cy="12" r="9"/>' +
    '<path d="M5.6 5.6l12.8 12.8"/></svg>',
  user:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linecap="round" stroke-linejoin="round">' +
    '<circle cx="12" cy="8" r="3.6"/>' +
    '<path d="M4.5 20.2c0-3.6 3.4-5.6 7.5-5.6s7.5 2 7.5 5.6"/></svg>',
  chevronDown:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" ' +
    'stroke-linecap="round" stroke-linejoin="round">' +
    '<polyline points="6 9.5 12 15.5 18 9.5"/></svg>',
  arrowLeft:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M19.5 12h-14"/><polyline points="11.5 6 5.5 12 11.5 18"/></svg>',
  logout:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M14 4h4a2 2 0 012 2v12a2 2 0 01-2 2h-4"/>' +
    '<polyline points="9 8 5 12 9 16"/><path d="M5 12h10"/></svg>',
  // 翻译:左边一个"文"字旁,右边一个 A —— 通用的翻译符号
  translate:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
    'stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M4 6h8M8 4v2"/>' +
    '<path d="M9.5 6c-.5 3-2.4 5.6-5.5 7.5"/>' +
    '<path d="M5.5 9c1.2 2.4 3 4.2 5.2 5.4"/>' +
    '<path d="M13.5 20.5l3.4-8.6 3.4 8.6"/><path d="M14.8 17.6h4.2"/></svg>',
};

// 造一个带 svg 的 span(图标是常量字符串,没有外部输入)
function iconSpan(key, size, filled) {
  const s = h("span", "ico");
  s.style.width = s.style.height = size + "px";
  s.innerHTML = ICONS[key] || "";
  if (filled) s.style.color = "inherit";
  return s;
}

// 站名。天文台是"观星的地方",而你的核心动作就是 star —— 比喻是顺的。
// 而且这个词**完全不含 "star"**,绕开了 GitHub 语境里的一个坑:
// 那边 "stargazer" 字面意思是"给你 star 的人",拿它当工具名意思正好反了
// (当初查名字时就是这么否决掉 stargazer 的,见 DEVLOG)。
const APP_NAME = "Observatory";

const listEl = document.getElementById("list");
const statusEl = document.getElementById("status");
const detailEl = document.getElementById("detail");
const searchPageEl = document.getElementById("searchpage");
const toolbarEl = document.getElementById("toolbar");
const railEl = document.getElementById("rail");
const titleEl = document.getElementById("pagetitle");
const pageBackEl = document.getElementById("pageback");
const tokenWarnEl = document.getElementById("tokenwarn");

// 页头的返回按钮(只在详情页出现,在标题左边)
pageBackEl.appendChild(iconSpan("arrowLeft", 22));
pageBackEl.onclick = () => {
  if (history.length > 1) history.back();
  else navigate("#/recommend");
};

let opinions = {};
let scrollTo = null;   // 详情页渲染完后要滚到哪(从评论按钮进来时用)
let currentUser = { logged_in: false };   // 当前登录的人(renderUserMenu 会更新它)

// 只放"不进 URL"的界面状态。页面 / 标签 / 搜索词都从 URL 读,URL 是唯一事实来源。
const state = {
  tab: "recommend",
  sort: "similarity",
  tags: [],
  offset: 0,
  hasMore: true,
  q: "",
  scope: "local",
  returnHash: "#/trending",   // 点进标签之前在哪,清空标签后回哪儿去。存**完整 hash**,见 toggleTag()
  followQ: "",              // 已关注页的搜索词(只搜已关注的人)
  followSort: "name",       // name | recent | oldest
  tagQ: "",                 // 标签页的搜索词(只搜**标签名**,不是搜仓库)
  searchSort: "relevance",  // 搜索页排序:relevance | stars | name | pushed
  starredView: "list",      // 已收藏页:list(仓库卡片) | status(它们现在怎么样了)
  starredSort: "growth",    // status 视图的排序:growth | stale | recent | stars
  // ---- 兔子洞(分站)----
  // 这几个都从 URL 读,和主站的标签/搜索一个道理:URL 是唯一事实来源,
  // 这样浏览器前进后退能用,分享出去的链接也对得上。
  acgSub: "list",           // list | tags
  acgSort: "stars",
  acgQ: "",                 // 洞里的搜索词
  acgTags: [],              // 洞里选中的标签(之间是「与」)
  acgOffset: 0,             // 下面两个给"下滑加载更多"用
  acgHasMore: true,
};

// 二次元分站的皮肤开关。进 /acg 换上,回主站脱掉。
//
// 为什么存在模块变量里而不是 state 里:详情页要**保持**它 ——
// 从分站点进一个仓库,不该突然换回主站的配色。而 state.tab 那时是 "detail",
// 光看它区分不出"从哪儿进来的"。
let acgZone = false;

function syncZone(tab) {
  const was = acgZone;
  if (tab === "acg") acgZone = true;
  else if (tab !== "detail") acgZone = false;   // 详情页不改变分区
  document.body.classList.toggle("acg", acgZone);
  // 进/出分站时**整套竖栏换掉** —— 它是"另一个地方",导航当然不一样。
  // 只在真的切换时才重建:每次 loadList 都重建会把悬停状态和动画打断。
  if (was !== acgZone) buildRail();
}
const PAGE = 30;
const SORTS = ["trending", "stars", "pushed", "name"];
const RECOMMEND_SORTS = ["similarity", "stars", "name"];
// 搜索结果的排序。relevance = 相关度:
//   本地库是"命中位置分级"(名字 > 描述 > 标签 > README),
//   全站是 GitHub 自己给的顺序。两者都叫"相关度",因为对用户来说是一回事。
const SEARCH_SORTS = ["relevance", "stars", "name", "pushed"];
const TABS = ["trending", "recommend", "tags", "starred", "search", "following", "acg"];
const sortsFor = (tab) => (tab === "recommend" ? RECOMMEND_SORTS : SORTS);

const NAV = [
  ["recommend", "tab_recommend", "spark"],
  ["trending", "tab_trending", "trending"],
  ["search", "tab_search", "search"],
  ["tags", "tab_tags", "tag"],
  ["starred", "tab_starred", "star"],
  ["following", "tab_following", "user"],
];
// 分站入口**不放在这儿** —— 它单独挂在竖栏最下面(刷新上面那一格),
// 中间隔着一段留白。见 buildRail()。
// 位置本身就是一句说明:"它和上面那六个不是一类东西"。

function h(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function nfmt(n) {
  if (n === null || n === undefined) return "?";
  return n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n);
}

const ownerOf = (fullName) => (fullName || "").split("/")[0];

// 头像一律走**我们自己的** /api/avatar,不要直连 github.com。
//
// 直连是这次查性能查出来的最大瓶颈:
//   · github.com 是**另一个域名** —— 浏览器要重新 DNS / TCP / TLS,而且都得走代理;
//   · github.com/<用户>.png 还会 **302 跳**到 avatars.githubusercontent.com,
//     等于每次两轮往返;
//   · 一页 30 张卡 = 60 次跨域往返。实测**单个头像 20 秒都拿不到**(直接超时),
//     而服务端出一个列表只要 0.01 秒 —— 页面的时间几乎全耗在等头像上。
//
// 走自己的域名之后:复用页面已经建好的连接、没有跳转链,而且服务端抓过一次就落盘,
// 之后是本地读文件。size 参数不再往 URL 上带(服务端统一缓存 80px 那份,
// 各种显示尺寸都够用)—— 带着它反而会把缓存拆成好几份。
function avatarImg(owner, size) {          // eslint-disable-line no-unused-vars
  const img = document.createElement("img");
  img.className = "avatar";
  img.src = "/api/avatar/" + encodeURIComponent(owner);
  img.alt = owner;
  img.loading = "lazy";
  img.referrerPolicy = "no-referrer";
  img.onerror = () => { img.removeAttribute("src"); };
  return img;
}

function ownerLink(owner) {
  const wrap = h("span", "owner");
  wrap.appendChild(avatarImg(owner, 32));
  const a = h("a", "owner-link", owner);     // 只写名字 —— "作者"两个字是废话
  a.href = "https://github.com/" + owner;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  wrap.appendChild(a);
  return wrap;
}

// ---- 自绘下拉 ----
// 原生 <select> 展开后那一列是操作系统画的 —— 圆角改不了,
// color-scheme 只能改颜色。想要圆角就得自己画一个。
function makeSelect(options, value, onChange) {
  const wrap = h("div", "sel");
  const cur = options.find(o => o[0] === value) || options[0];

  const btn = h("button", "sel-btn");
  btn.appendChild(h("span", null, cur[1]));
  btn.appendChild(h("span", "sel-caret", "▾"));
  wrap.appendChild(btn);

  const menu = h("div", "sel-menu");
  options.forEach(([v, text]) => {
    const item = h("div", "sel-item" + (v === value ? " on" : ""), text);
    item.onclick = (e) => {
      e.stopPropagation();
      wrap.classList.remove("open");
      if (v !== value) onChange(v);
    };
    menu.appendChild(item);
  });
  wrap.appendChild(menu);

  btn.onclick = (e) => {
    e.stopPropagation();
    const wasOpen = wrap.classList.contains("open");
    document.querySelectorAll(".sel.open").forEach(s => s.classList.remove("open"));
    if (!wasOpen) wrap.classList.add("open");
  };
  return wrap;
}

// 点页面任何地方都收起下拉
document.addEventListener("click", () => {
  document.querySelectorAll(".sel.open").forEach(s => s.classList.remove("open"));
});

// ---- 路由 ----
function navigate(hash) {
  if (location.hash === hash) route();     // 同址不触发 hashchange,手动跑一次
  else location.hash = hash;
}

const tagHash = (tags) => "#/tag/" + tags.map(encodeURIComponent).join(",");

function currentRoute() {
  const raw = location.hash.replace(/^#\/?/, "");
  const qi = raw.indexOf("?");
  return {
    parts: (qi >= 0 ? raw.slice(0, qi) : raw).split("/").filter(Boolean),
    qs: new URLSearchParams(qi >= 0 ? raw.slice(qi + 1) : ""),
  };
}

// 每个页面能排的字段不同。切页面时如果当前排序在目标页面不合法,就换成默认的。
// 否则会把 "similarity"(推荐页专有的选项)发给 Trending 或标签页,接口直接 422。
//
// ⚠️ 抽成函数是因为上次我只在 Trending 那条分支里修了,漏了标签页 ——
// 表现就是"从推荐页点标签会报错"。**这种校验要在所有入口都过一遍**,
// 写在分支里迟早漏。
function fixSortFor(tab) {
  if (!sortsFor(tab).includes(state.sort)) {
    state.sort = tab === "recommend" ? "similarity" : "trending";
  }
}

// 解 URL 里的百分号编码,解不出来就当原样 —— 绝不抛。
//
// decodeURIComponent("%") 会抛 URIError。而它是在 **hashchange 回调**里被调用的,
// 没人接这个异常 —— route() 当场中断,页面停在旧内容,只在控制台留一行错,
// 用户看到的是"我输了个地址,啥也没发生"。
// 手敲一个 #/tag/% 就能触发。
function safeDecode(s) {
  try { return decodeURIComponent(s); } catch (_) { return s; }
}

function route() {
  const { parts, qs } = currentRoute();
  const head = parts[0] || "recommend";

  // #/repo/owner/name ,可选 ?to=comments 表示进来后滚到评论区
  if (head === "repo" && parts.length >= 3) {
    state.tab = "detail";
    scrollTo = qs.get("to") || null;
    setActiveTab(null);
    showDetail(safeDecode(parts[1]) + "/" + safeDecode(parts[2]));
    return;
  }
  scrollTo = null;

  // #/tag/a,b
  if (head === "tag" && parts[1]) {
    state.tags = parts[1].split(",").map(safeDecode).filter(Boolean);
    state.tab = "tag";
    fixSortFor(state.tab);          // ← 补上:这条分支以前漏了,从推荐页点标签就报错
    setActiveTab(null);
    setTitle("tab_tags");
    loadList();
    return;
  }

  // #/acg 或 #/acg/tags —— 兔子洞(分站)
  // ⚠️ 必须排在下面那行 `TABS.includes(head)` **前面**:先把 acg 拦下来,
  // 顺便把子页(parts[1])和筛选条件(q/tag/sort)解析掉。
  // 靠 TABS 那套是不行的 —— 它只认一个扁平的表,分不出 `acg/tags`。
  if (head === "acg") {
    state.tab = "acg";
    state.acgSub = parts[1] === "tags" ? "tags" : "list";
    state.acgTags = (qs.get("tag") || "").split(",").map(safeDecode).filter(Boolean);
    state.acgQ = qs.get("q") || "";
    // 有搜索词时默认按**相关度**排 —— 按星数排的话,搜出来的前几名会是
    // "最火但只是顺带提过这个词"的仓库(这个坑在主站搜索那边踩过)。
    state.acgSort = qs.get("sort") || (state.acgQ ? "relevance" : "stars");
    state.tags = [];                  // 别把主站的标签筛选带进来
    state.offset = 0;
    syncZone("acg");                  // 先切分区(会重建竖栏),再标高亮
    setActiveTab(state.acgSub === "tags" ? "acg-tags" : "acg");
    loadList();
    return;
  }

  state.tags = [];
  state.tab = TABS.includes(head) ? head : "recommend";
  fixSortFor(state.tab);

  if (state.tab === "search") {
    state.q = qs.get("q") || "";
    state.scope = qs.get("scope") || "local";
  }

  // 推荐页改成"滚到底自动加载"了,没有"第几批"这个概念 —— 每次进来都从头看
  state.offset = 0;
  // ⚠️ syncZone 必须在 setActiveTab **之前** —— 它会重建整条竖栏,
  // 顺序反了的话,刚刚标好的高亮会被新竖栏冲掉(页面看着像没选中任何一项)。
  syncZone(state.tab);
  setActiveTab(state.tab);
  loadList();
}

window.addEventListener("hashchange", route);

// ---- 竖导航 ----
function railButton(iconKey, label, onClick, tab) {
  const b = h("button", "rail-btn");
  if (tab) b.dataset.tab = tab;
  const ico = h("span", "ico");
  if (iconKey.charAt(0) === "/") {
    // 以 / 开头 = 图片路径,不是 ICONS 里的键。
    //
    // 为什么这里用图片而不是线条图标:线条图标里画一个"一眼认得出的少女"
    // 试了四版都不行(渲染出来依次像幽灵 / 外星人 / 披斗篷的人 / 熊脸)——
    // 28px 里画人本来就是个硬骨头。既然手上有张明确无误的图,就别跟 SVG 较劲了。
    const im = document.createElement("img");
    im.src = iconKey;
    im.alt = "";
    im.className = "rail-img";
    ico.appendChild(im);
  } else {
    ico.innerHTML = ICONS[iconKey];    // 常量 SVG,没有外部输入
  }
  b.appendChild(ico);
  b.appendChild(h("span", "rail-label", label));
  b.title = label;
  b.onclick = onClick;
  return b;
}

function buildRail() {
  railEl.replaceChildren();

  const brand = h("button", "rail-brand");
  brand.title = APP_NAME;
  const bico = h("span", "ico");
  if (acgZone) {
    // 进了洞,站标也换成洞自己的 —— 从"天文台"变成这个角色本身。
    // 这是"另一个站"最直接的信号:连左上角的标都换了。
    const im = document.createElement("img");
    im.src = "/rabbit_hole_icon.png";
    im.alt = "";
    im.className = "brand-img";
    bico.appendChild(im);
  } else {
    // 主站站标:icons8 那张天文台。
    // ⚠️ 它是**黑线 + 透明底**的 PNG,而站点默认是深色主题 ——
    // 黑图标贴在近黑背景上等于看不见。CSS 里靠 .brand-obs 在深色下反转成白
    // (只反转这一张:兔子洞那张是彩色插画,反转就毁了)。
    const im = document.createElement("img");
    im.src = "/icons8-observatory-100.png";
    im.alt = "";
    im.className = "brand-img brand-obs";
    bico.appendChild(im);
  }
  brand.appendChild(bico);
  brand.appendChild(h("span", "rail-label", APP_NAME));
  brand.onclick = () => navigate("#/recommend");
  railEl.appendChild(brand);

  if (acgZone) {
    // ---- 兔子洞的导航 ----
    // 第一项是**回主站**。放第一项是有意的:进来之后,"出去"是这个站里
    // 最基本的一个动作 —— 只靠浏览器后退键的话,很多人根本想不到。
    // (最后那个参数传 null:它不是一个"当前页",不该有高亮态。)
    railEl.appendChild(railButton("arrowLeft", t("acg_back"),
                                  () => navigate("#/recommend"), null));
    railEl.appendChild(railButton("/rabbit_head.png", t("tab_acg"),
                                  () => navigate("#/acg"), "acg"));
    railEl.appendChild(railButton("tag", t("acg_tags"),
                                  () => navigate("#/acg/tags"), "acg-tags"));
  } else {
    NAV.forEach(([tab, labelKey, iconKey]) => {
      railEl.appendChild(railButton(iconKey, t(labelKey), () => navigate("#/" + tab), tab));
    });
  }

  railEl.appendChild(h("div", "rail-spacer"));

  // 分站入口只在**主站**显示。已经在洞里的时候它没有意义 ——
  // 上面那个"兔子洞"就是它,再挂一个会出现两个一模一样的按钮。
  if (!acgZone) {
    railEl.appendChild(railButton("/rabbit_head.png", t("tab_acg"),
                                  () => navigate("#/acg"), "acg"));
  }

  // 底部这个"刷新"就是单纯重新拉一次当前页面,不动批次
  railEl.appendChild(railButton("refresh", t("refresh"), () => loadList()));

  // 语言:显示**当前**语言(和外观按钮同一套逻辑 —— 显示现在是什么,不是点了会变成什么)
  railEl.appendChild(railButton("globe", t(lang === "zh" ? "lang_zh" : "lang_en"), () => {
    lang = lang === "zh" ? "en" : "zh";
    localStorage.setItem("ui_lang", lang);
    buildRail();
    renderNavMenu();
    renderTokenWarning();     // 提示条也要跟着换语言 —— 不然它会是页面上唯一没变的
    route();
  }));

  // 外观:同样显示**当前**模式
  const theme = currentTheme();
  railEl.appendChild(railButton(
    theme === "light" ? "sun" : "moon",
    t(theme === "light" ? "theme_light" : "theme_dark"),
    () => {
      const next = theme === "light" ? "dark" : "light";
      localStorage.setItem("theme", next);
      applyTheme(next);
      buildRail();
    }));
}

function setActiveTab(tab) {
  document.querySelectorAll(".rail-btn[data-tab]").forEach(b => {
    b.classList.toggle("active", b.dataset.tab === tab);
  });
}

function setTitle(key) {
  titleEl.textContent = t(key);
  pageBackEl.title = t("back");
}

function showPageBack(show) {
  pageBackEl.style.display = show ? "inline-flex" : "none";
}

function toggleTag(tag) {
  if (!state.tags.length) {
    // 记住"从哪儿点进标签的",清空标签后好回去。
    //
    // ⚠️ 存的是**完整 hash**,不是 state.tab。
    // state.tab 的取值不止"列表页那几种":详情页是 "detail"、搜索页是 "search"。
    // 存 tab 名再拼成 "#/" + tab 会得到两个坏地址:
    //   #/detail —— 不在 TABS 里,路由会当成未知页面把人甩回推荐页
    //   #/search —— 能打开,但 q 参数没了,搜索词和结果全丢
    // hash 天生就是"可以直接 navigate 的",没有这个拼接问题。
    const cur = location.hash || "#/trending";
    state.returnHash = cur.startsWith("#/tag/") ? "#/trending" : cur;
  }
  const next = state.tags.includes(tag)
    ? state.tags.filter(x => x !== tag)
    : state.tags.concat(tag);
  navigate(next.length ? tagHash(next) : (state.returnHash || "#/trending"));
}

// ---- 条目底部的操作行 ----
// 心(感兴趣) · 评论数 · 星数 · 更多。全是图标,状态靠颜色和空心/实心 —— 不写文字。
function postActions(r, node, opts = {}) {
  const wrap = h("div", "actions");
  const note = h("span", "reason", opts.reasonText || "");
  if (opts.reasonTitle) note.title = opts.reasonTitle;

  // 心:感兴趣
  const like = h("button", "icon-btn like");
  like.title = t("interested");

  // 评论数:点了进详情,并滚到评论那里
  const cmt = h("button", "icon-btn");
  cmt.title = t("comments_go");
  cmt.appendChild(iconSpan("comment", 21));
  cmt.appendChild(h("span", null, String(r.comment_count || 0)));
  cmt.onclick = (e) => {
    e.stopPropagation();
    navigate("#/repo/" + r.full_name + "?to=comments");
  };

  // 星数:点了真的去 GitHub star(不是本地标记)
  const st = h("button", "icon-btn");
  st.title = t("star_go");
  st.appendChild(iconSpan("star", 21));
  st.appendChild(h("span", null, nfmt(r.stargazers_count)));
  st.onclick = async (e) => {
    e.stopPropagation();
    st.disabled = true;
    try {
      const res = await fetch(API + "/api/star/" + r.full_name,
                              { method: "POST", credentials: "include" });
      const out = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(out.detail || ("HTTP " + res.status));
      st.classList.add("on");
      note.textContent = t("starred_ok");
    } catch (err) {
      note.textContent = err.message;      // 比如 token 没权限,把原话显示出来
      refreshTokenWarning();               // 万一是授权失效,让顶部提示条立刻出现
    } finally {
      st.disabled = false;
    }
  };

  const more = moreMenu(r, paint, note, opts.topRight);

  function paint() {
    const cur = opinions[r.full_name];
    const on = cur === "interested";
    const off = cur === "not_interested";
    like.classList.toggle("on", on);
    like.replaceChildren(iconSpan(on ? "heartFilled" : "heart", 21));
    node.classList.toggle("dim", off);
    if (more.sync) more.sync();            // 菜单里的"取消不感兴趣"要跟着状态变字
  }

  // 再点一次 = 取消表态(写一条 neutral 把之前的标记撤回)
  like.onclick = (e) => {
    e.stopPropagation();
    vote(r.full_name,
         opinions[r.full_name] === "interested" ? "neutral" : "interested",
         paint, note);
  };

  wrap.appendChild(like);
  wrap.appendChild(cmt);
  wrap.appendChild(st);
  // 放哪儿由调用方决定:列表里钉卡片右上角;详情页挂到页头 Releases 右边
  if (opts.moreHost) opts.moreHost.appendChild(more);
  else if (opts.topRight) node.appendChild(more);
  else wrap.appendChild(more);

  // note 永远挂进 DOM,哪怕现在没内容。
  //
  // 以前这里是 `if (opts.reasonText) wrap.appendChild(note)` ——
  // 但 Trending / 搜索 / 已收藏 / 详情页的条目**本来就没有"推荐理由"**,
  // 于是 note 成了一个游离节点(创建了、但从没进过文档)。
  // 点星失败(token 权限不足那段完整的报错文案)、投票失败、复制链接的提示
  // 全都写进了这个看不见的元素里 —— 用户侧的表现是"我明明点了,界面毫无反应",
  // 而且控制台一声不吭。这类问题最难查,因为根本没有错误可看。
  //
  // 空着的 .reason 只是个 12px 的灰色 span(左边距 6px),挂着不占地方。
  wrap.appendChild(note);
  paint();
  return wrap;
}

// "更多"菜单:复制链接 / 不感兴趣。
// 复用下拉面板那套样式和"点外面收起"的行为。
function moreMenu(r, paint, note, topRight) {
  const wrap = h("div", "sel more" + (topRight ? " topright" : ""));
  const btn = h("button", "icon-btn");
  btn.title = t("more");
  btn.appendChild(iconSpan("more", 21));
  wrap.appendChild(btn);

  const menu = h("div", "sel-menu");
  const addItem = (iconKey, labelText, onClick) => {
    const item = h("div", "sel-item");
    item.appendChild(iconSpan(iconKey, 15));
    const lab = h("span", null, labelText);
    item.appendChild(lab);
    item.onclick = (e) => {
      e.stopPropagation();
      wrap.classList.remove("open");
      onClick();
    };
    menu.appendChild(item);
    return lab;
  };

  addItem("copy", t("copy_link"), async () => {
    const url = r.html_url || ("https://github.com/" + r.full_name);
    try {
      await navigator.clipboard.writeText(url);
      note.textContent = t("copied");
    } catch {
      note.textContent = url;     // 剪贴板不可用就把地址显示出来,让人手动复制
    }
  });

  const banLabel = addItem("ban", "", () => {
    const off = opinions[r.full_name] === "not_interested";
    vote(r.full_name, off ? "neutral" : "not_interested", paint, note);
  });

  wrap.sync = () => {
    const off = opinions[r.full_name] === "not_interested";
    banLabel.textContent = t(off ? "un_not_interested" : "not_interested");
  };

  wrap.appendChild(menu);
  btn.onclick = (e) => {
    e.stopPropagation();
    const wasOpen = wrap.classList.contains("open");
    document.querySelectorAll(".sel.open").forEach(s => s.classList.remove("open"));
    if (!wasOpen) wrap.classList.add("open");
  };
  return wrap;
}

async function vote(fullName, action, paint, note) {
  if (opinions[fullName] === action) return;
  try {
    const res = await fetch(API + "/api/events", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name: fullName, action: action }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || ("HTTP " + res.status));
    }
    opinions[fullName] = action;
    paint();
  } catch (e) {
    note.textContent = t("fail") + e.message;
  }
}

// 翻译按钮:点了把 getText() 的内容翻成当前界面语言,再点一次还原。
// 介绍和 README 共用这一段 —— 逻辑只有一份,不会改了一处忘了另一处。
function translateButton(getText, setText) {
  const btn = h("button", "icon-btn translate-btn");
  btn.title = t("translate");
  btn.appendChild(iconSpan("translate", 16));

  let original = null;               // null 表示当前显示的是原文
  btn.onclick = async (e) => {
    e.stopPropagation();             // 别让整块点击把页面带走
    if (original !== null) {         // 再点一次:还原
      setText(original);
      original = null;
      return;
    }
    btn.disabled = true;
    try {
      const to = lang === "en" ? "en" : "zh";
      const d = await getJSON("/api/translate?to=" + to +
                              "&text=" + encodeURIComponent(getText()));
      original = getText();
      setText(d.translated);
    } catch (err) {
      original = getText();          // 先把原文记住,出错了也能还原
      setText(t("translate_fail") + err.message);
    } finally {
      btn.disabled = false;
    }
  };
  return btn;
}

// 介绍 + 右下角的翻译按钮
function introBlock(text) {
  const wrap = h("div", "intro-wrap");
  const p = h("p", "intro", text);
  wrap.appendChild(p);
  wrap.appendChild(translateButton(() => p.textContent,
                                  (s) => { p.textContent = s; }));
  return wrap;
}

// ---- 条目 ----
function repoPost(r, opts = {}) {
  const node = h("article", "post");
  const owner = ownerOf(r.full_name);

  // 点整块进详情页。放过按钮 / 链接 / 标签 —— 它们在卡片内部各有各的行为。
  node.onclick = (e) => {
    if (e.target.closest("button, a, .topic, .sel")) return;
    navigate("#/repo/" + r.full_name);
  };

  const av = h("div", "post-avatar");
  av.appendChild(avatarImg(owner, 80));
  node.appendChild(av);

  const body = h("div", "post-body");
  const head = h("div", "post-head");
  const nameLink = h("a", "name", r.full_name);
  nameLink.href = "#/repo/" + r.full_name;      // 真链接:中键/右键新标签页也能用
  nameLink.onclick = (e) => { e.preventDefault(); e.stopPropagation(); navigate("#/repo/" + r.full_name); };
  head.appendChild(nameLink);

  const bits = [];
  if (r.language) bits.push(r.language);
  // 星数不放这儿 —— 下面操作行里的星图标已经带数量了,同一张卡上写两遍是重复
  if (r.delta !== undefined && r.delta !== null) bits.push("▲ " + r.delta);
  if (r.similarity !== undefined) bits.push(t("similarity") + " " + r.similarity.toFixed(3));
  if (r.starred_at) bits.push(r.starred_at.slice(0, 10));
  head.appendChild(h("span", "muted", bits.join(" · ")));
  body.appendChild(head);

  const desc = (r.description || "").trim();
  const intro = (r.intro || "").trim();
  const distinct = intro && intro !== desc;
  if (distinct && desc) body.appendChild(h("p", "desc", desc));
  const mainText = distinct ? intro : desc;
  if (mainText) body.appendChild(introBlock(mainText));

  if (r.topics && r.topics.length) {
    const box = h("div", "topics");
    r.topics.slice(0, 8).forEach(tag => {
      const on = state.tags.includes(tag);
      const chip = h("span", "topic clickable" + (on ? " on" : ""), tag);
      chip.title = on ? t("tag_remove") : t("tag_add");
      chip.onclick = (e) => { e.stopPropagation(); toggleTag(tag); };
      box.appendChild(chip);
    });
    body.appendChild(box);
  }

  // 推荐理由:图标 + 仓库名就够了(星=因为你 star 过,心=因为你点过感兴趣)。
  // 完整说法放 title,鼠标停上去才显示 —— 一行字挂在卡片上太占地方。
  let reasonText = "";
  let reasonTitle = "";
  if (r.because_of) {
    const liked = r.because_kind === "interested";
    reasonText = (liked ? "♥ " : "★ ") + r.because_of;
    reasonTitle = (liked ? t("because_liked") : t("because_starred")) + r.because_of;
  } else if (r.because_kind === "explore") {
    // 探索位:它**本来就不像**你 star 过的东西,所以没有"因为你…"可写。
    // 硬编一个理由是骗人 —— 这里老实说"换换口味",
    // 顺便在 title 里把"凭什么推它"(多少人在用 / 最近涨了多少)交代清楚。
    reasonText = "✨ " + t("reason_explore");
    reasonTitle = r.delta
      ? t("reason_explore_growth", nfmt(r.delta))
      : t("reason_explore_plain");
  }
  if (opts.feedback) {
    body.appendChild(postActions(r, node, { reasonText, reasonTitle, topRight: true }));
  }

  node.appendChild(body);
  return node;
}

// ---- 工具栏 ----
function renderToolbar() {
  toolbarEl.replaceChildren();

  // 推荐页不再有"换一批 / 上一批"按钮 —— 改成滚到底自动加载(见 loadMoreRecommend)

  if (state.tab === "trending" || state.tab === "tag" || state.tab === "recommend") {
    toolbarEl.appendChild(makeSelect(
      sortsFor(state.tab).map(v => [v, t("sort_" + v)]),
      state.sort,
      (v) => { state.sort = v; loadList(); }));
  }

  // 已关注页:搜索框(只搜已关注的人)+ 排序
  if (state.tab === "following") {
    const input = document.createElement("input");
    input.type = "search";
    input.className = "toolbar-search";
    input.placeholder = t("follow_search");
    input.value = state.followQ;
    input.onkeydown = (e) => {
      if (e.key === "Enter") { state.followQ = input.value.trim(); loadList(); }
    };
    toolbarEl.appendChild(input);
    toolbarEl.appendChild(makeSelect(
      [["name", t("follow_sort_name")],
       ["recent", t("follow_sort_recent")],
       ["oldest", t("follow_sort_oldest")]],
      state.followSort,
      (v) => { state.followSort = v; loadList(); }));
  }

  // 标签页:搜索框(只搜**标签名**,不是搜仓库)
  //
  // 用 Enter 触发而不是"边打边筛":和已关注页那个搜索框保持一致 ——
  // 同一个站里两个搜索框行为不同,比哪个方案本身更让人困惑。
  // 后端按标签名筛(见 /api/tags 的 q 参数),不是把标签拉回来在前端滤。
  if (state.tab === "tags") {
    const input = document.createElement("input");
    input.type = "search";
    input.className = "toolbar-search";
    input.placeholder = t("tag_search");
    input.value = state.tagQ;
    input.onkeydown = (e) => {
      if (e.key === "Enter") { state.tagQ = input.value.trim(); loadList(); }
    };
    toolbarEl.appendChild(input);
  }

  // 已收藏页:两种看法。默认是"列表"(和别处一样的卡片),
  // 切到"现状"就换个角度 —— 同一批仓库,看的是它们**现在**怎么样
  // (还在更新吗、还在涨吗),而不是它们长什么样。
  if (state.tab === "starred") {
    toolbarEl.appendChild(makeSelect(
      [["list", t("starred_view_list")], ["status", t("starred_view_status")]],
      state.starredView,
      (v) => { state.starredView = v; loadList(); }));
    if (state.starredView === "status") {
      toolbarEl.appendChild(makeSelect(
        [["growth", t("status_sort_growth")],
         ["stale", t("status_sort_stale")],
         ["recent", t("status_sort_recent")],
         ["stars", t("status_sort_stars")]],
        state.starredSort,
        (v) => { state.starredSort = v; loadList(); }));
    }
  }

  // 兔子洞的工具栏:搜索 + 排序 + 已选标签。
  // 只在列表子页出现 —— 标签云页上没有"搜索/排序"这回事。
  if (state.tab === "acg" && state.acgSub === "list") {
    const input = document.createElement("input");
    input.type = "search";
    input.className = "toolbar-search";
    input.placeholder = t("acg_search");
    input.value = state.acgQ;
    input.onkeydown = (e) => {
      if (e.key === "Enter") navigate(acgHash({ q: input.value.trim() }));
    };
    toolbarEl.appendChild(input);

    // "相关度"只在**有搜索词**时才出现在选项里 ——
    // 没搜索词时没有"相关不相关"可言(那个排序靠 SQL 里的 rank 列,压根不存在)。
    const sortOpts = [["stars", t("sort_stars")], ["pushed", t("sort_pushed")],
                      ["name", t("sort_name")], ["added", t("sort_added")]];
    if (state.acgQ) sortOpts.unshift(["relevance", t("sort_relevance")]);

    toolbarEl.appendChild(makeSelect(sortOpts, state.acgSort,
                                     (v) => navigate(acgHash({ sort: v }))));

    // 已选标签:只列标签本身、点一下移除(和主站那套一致)
    state.acgTags.forEach(tag => {
      const chip = h("span", "chip on", tag);
      chip.title = t("tag_remove");
      chip.onclick = () => navigate(
        acgHash({ tag: state.acgTags.filter(x => x !== tag) }));
      toolbarEl.appendChild(chip);
    });
  }

  state.tags.forEach(tag => {
    const chip = h("span", "chip on", tag);
    chip.title = t("tag_remove");
    chip.onclick = () => toggleTag(tag);
    toolbarEl.appendChild(chip);
  });
}

// ---- 标签云 ----
function renderTagCloud(d) {
  listEl.replaceChildren();
  statusEl.textContent = "";

  if (!d.items.length) {
    // 搜不到 vs 库里本来就没标签,是两回事 —— 提示得分开
    statusEl.textContent = d.q ? t("tag_no_match") : t("no_data");
    return;
  }

  const wrap = h("div");
  // 搜索时标题说"匹配了多少个";没搜时说的是覆盖率。
  // 两个数说的**不是同一件事**(一个是筛选结果数,一个是全库覆盖),
  // 混在一起会让人以为搜了一下覆盖率就变了。
  wrap.appendChild(h("div", "section-title",
    d.q ? t("tag_search_hit", d.q, d.count)
        : t("tagcloud_title", d.count, d.tagged_repos, d.total_repos)));

  const cloud = h("div", "topics");
  cloud.style.marginTop = "0";
  d.items.forEach(item => {
    const chip = h("span", "topic clickable", `${item.tag} ${item.n}`);
    chip.title = t("tag_add");
    chip.onclick = () => toggleTag(item.tag);
    cloud.appendChild(chip);
  });
  wrap.appendChild(cloud);
  listEl.appendChild(wrap);
}

// ---- 二次元分站 ----
// 只收某个主题的仓库。名单由 fetch_acg.py 按关键词搜出来,存在 acg_repos 表。
//
// "小分站"的意思就是**功能少**:一个列表 + 一个排序,点进去用同一个详情页。
// 不做推荐、不做标签筛选、不做搜索 —— 那些等真用起来、发现缺了再加,
// 一上来全铺开反而看不出哪部分有用。
// 把洞里的筛选条件拼成 hash。**所有筛选都走 URL** ——
// 和主站一个道理:URL 是唯一事实来源,前进后退能用,链接也分享得出去。
function acgHash({ q = state.acgQ, tag = state.acgTags,
                   sort = state.acgSort } = {}) {
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (tag && tag.length) p.set("tag", tag.join(","));
  if (sort && sort !== "stars") p.set("sort", sort);   // 默认值不往 URL 里塞
  const s = p.toString();
  return "#/acg" + (s ? "?" + s : "");
}

// 洞里的列表 URL。带 offset 是为了"下滑加载更多"。
function acgQuery(offset) {
  const p = new URLSearchParams({ sort: state.acgSort, limit: PAGE, offset });
  if (state.acgQ) p.set("q", state.acgQ);
  state.acgTags.forEach(x => p.append("tag", x));
  return "/api/acg?" + p.toString();
}

async function renderAcg() {
  const d = await getJSON(acgQuery(0));
  listEl.replaceChildren();

  if (!d.items.length) {
    // 搜不到 和 名单本来是空的,是两回事 —— 提示要分开
    statusEl.textContent = (state.acgQ || state.acgTags.length)
      ? t("acg_no_match") : t("no_data");
    return;
  }

  // matched = 当前筛选条件下有多少条。显示它而不是名单总数,
  // 不然筛完还挂着 4608,用户会以为筛选没生效。
  statusEl.textContent = t("acg_summary", d.matched);

  state.acgOffset = d.count;
  state.acgHasMore = d.count < d.matched;

  // feedback: true —— 那行图标(心 / 评论数 / 星 / 更多)**全是由 postActions 渲染的**,
  // 关掉它整行都没了,不只是"少个心"。
  d.items.forEach(r => listEl.appendChild(repoPost(r, { feedback: true })));
  appendMoreSentinel(state.acgHasMore);
}

// 滚到底自动加载下一批。逻辑和推荐页那套一样,区别只是查询参数不同。
async function loadMoreAcg() {
  if (loadingMore || !state.acgHasMore || state.tab !== "acg"
      || state.acgSub !== "list" || !moreSentinel) return;
  loadingMore = true;
  const sentinel = moreSentinel;              // 抓住这一刻的哨兵,后面要验它还在不在
  const offset = state.acgOffset;
  sentinel.textContent = t("loading");
  try {
    const d = await getJSON(acgQuery(offset));
    // await 之后世界可能已经变了(切页/改筛选/按了后退)——
    // 三个都要查,理由和推荐页那边一样
    if (state.tab !== "acg" || state.acgSub !== "list"
        || moreSentinel !== sentinel || !sentinel.isConnected) return;

    state.acgOffset = offset + d.count;
    state.acgHasMore = offset + d.count < d.matched;
    d.items.forEach(r =>
      listEl.insertBefore(repoPost(r, { feedback: true }), sentinel));
    sentinel.textContent = state.acgHasMore ? "" : t("list_end");
  } catch (e) {
    if (!needLogin(e)) statusEl.textContent = t("error") + e.message;
  } finally {
    loadingMore = false;
  }
}

// 洞里的标签云。点一个标签 → 回到列表并只看带它的 —— 不另开筛选页,
// 分站就这么点东西,多一层页面反而绕。
async function renderAcgTags() {
  const d = await getJSON("/api/acg/tags?limit=300");
  listEl.replaceChildren();

  if (!d.items.length) {
    statusEl.textContent = t("no_data");
    return;
  }
  statusEl.textContent = t("acg_tag_title", d.count);

  const wrap = h("div");
  const cloud = h("div", "topics");
  cloud.style.marginTop = "0";
  d.items.forEach(item => {
    const chip = h("span", "topic clickable", `${item.tag} ${item.n}`);
    chip.title = t("tag_add");
    chip.onclick = () => navigate(acgHash({ tag: [item.tag] }));
    cloud.appendChild(chip);
  });
  wrap.appendChild(cloud);
  listEl.appendChild(wrap);
}

// ---- 已收藏:现状 ----
// 同一批 star 过的仓库,换个角度看:**它们现在怎么样了**。
async function renderStarredStatus() {
  const d = await getJSON("/api/me/starred/status?sort=" + state.starredSort);
  listEl.replaceChildren();

  if (!d.items.length) {
    statusEl.textContent = t("no_data");
    return;
  }

  const hc = d.health_counts || {};
  statusEl.textContent = t("status_summary", d.count,
    hc.active || 0, hc.slowing || 0, hc.stale || 0);

  // 把"这个 +N 是什么"说清楚。不说的话,很自然会有人理解成
  // "从 star 到现在涨了多少" —— 而那个数我们**根本没有**。
  listEl.appendChild(h("div", "status-note muted", t("status_note")));

  const wrap = h("div", "status-list");
  d.items.forEach(x => {
    const row = h("a", "status-row");
    row.href = "#/repo/" + x.full_name;
    row.onclick = (e) => {
      e.preventDefault();
      navigate("#/repo/" + x.full_name);
    };

    // 左边一个颜色点表示"还活着吗" —— 不写文字,扫一眼就知道整体。
    // 但光有颜色,谁知道绿黄红各是什么意思?所以挂个 title 说明。
    const dot = h("span", "health-dot " + x.health);
    dot.title = t("health_" + x.health);
    row.appendChild(dot);

    const main = h("div", "status-main");
    main.appendChild(h("div", "name", x.full_name));
    main.appendChild(h("div", "status-sub",
      (x.language ? x.language + " · " : "") + "★" + nfmt(x.stargazers_count)));
    row.appendChild(main);

    const right = h("div", "status-right");
    if (x.delta === null || x.delta === undefined) {
      // 没数据就说没数据,别显示成 0 —— "涨了 0" 和 "不知道" 是两回事
      right.appendChild(h("div", "status-delta muted", t("status_delta_none")));
    } else {
      right.appendChild(h("div", "status-delta" + (x.delta > 0 ? " up" : ""),
        (x.delta > 0 ? "+" : "") + x.delta));
    }
    right.appendChild(h("div", "status-when muted",
      x.days_since_push === null || x.days_since_push === undefined
        ? t("health_unknown")
        : x.days_since_push === 0 ? t("days_today")
        : t("days_ago", x.days_since_push)));
    row.appendChild(right);

    wrap.appendChild(row);
  });
  listEl.appendChild(wrap);
}

// ---- 搜索页 ----
function searchBar() {
  const bar = h("div", "searchbar");
  const input = document.createElement("input");
  input.type = "search";
  input.placeholder = t("search_placeholder");
  input.value = state.q || "";

  const scope = makeSelect(
    [["local", t("scope_local")], ["github", t("scope_github")]],
    state.scope,
    (v) => {
      state.scope = v;
      if (state.q) navigate(searchHash(state.q, v));
    });

  const go = h("button", "btn primary", t("search_go"));
  const submit = () => {
    const q = input.value.trim();
    if (q) navigate(searchHash(q, state.scope));
  };
  input.addEventListener("keydown", e => { if (e.key === "Enter") submit(); });
  go.onclick = submit;

  bar.appendChild(input);
  bar.appendChild(scope);

  // 排序只在**有搜索词**的时候出现。
  // 搜索词为空时下面展示的是"发现"页(热门标签 / 上升最快 / 你 star 过的作者),
  // 那里没有"搜索结果"可排 —— 摆一个用不上的控件只会让人以为它坏了。
  if (state.q) {
    bar.appendChild(makeSelect(
      SEARCH_SORTS.map(v => [v, t("sort_" + v)]),
      state.searchSort,
      (v) => { state.searchSort = v; loadList(); }));
  }

  bar.appendChild(go);
  return bar;
}

const searchHash = (q, scope) =>
  "#/search?q=" + encodeURIComponent(q) + "&scope=" + encodeURIComponent(scope || "local");

// 从 star 列表里聚合出作者,按 star 过的仓库数排序。
// 注意:我们没有"关注"关系的数据 —— 这是**用 star 反推**"你在意哪些作者"。
function authorsSection(items, limit = 12) {
  if (!items || !items.length) return null;
  const count = {};
  items.forEach(r => {
    const o = ownerOf(r.full_name);
    count[o] = (count[o] || 0) + 1;
  });
  const authors = Object.entries(count).sort((a, b) => b[1] - a[1]).slice(0, limit);
  if (!authors.length) return null;

  const s = h("div", "section");
  s.appendChild(h("div", "section-title", t("discover_authors")));
  const grid = h("div", "author-grid");
  authors.forEach(([owner, n]) => {
    const a = h("a", "author");
    a.href = "https://github.com/" + owner;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.appendChild(avatarImg(owner, 56));
    a.appendChild(h("span", null, owner + (n > 1 ? " ×" + n : "")));
    grid.appendChild(a);
  });
  s.appendChild(grid);
  return s;
}

// 已关注:GitHub 的 following 列表(真实数据,由 sync_following.py 同步)
async function renderFollowing() {
  const p = new URLSearchParams({ limit: 2000, sort: state.followSort });
  if (state.followQ) p.set("q", state.followQ);
  const d = await getJSON("/api/me/following?" + p.toString());

  listEl.replaceChildren();
  if (!d.items.length) {
    statusEl.textContent = state.followQ ? t("follow_no_match") : t("following_empty");
    return;
  }
  statusEl.textContent = t("summary_following", d.count);

  d.items.forEach(u => {
    const row = h("a", "follow-row");
    row.href = u.html_url;
    row.target = "_blank";
    row.rel = "noopener noreferrer";

    // 一律走 avatarImg(→ /api/avatar),不用库里存的 avatar_url。
    // 那个 URL 指向 avatars.githubusercontent.com —— 又一个独立域名,
    // 一样要重新握手,而且绕不过代理。理由详见 avatarImg 上面的注释。
    row.appendChild(avatarImg(u.login, 88));

    const info = h("div", "follow-info");
    info.appendChild(h("div", "follow-login", u.login));
    if (u.name) info.appendChild(h("div", "follow-name", u.name));
    row.appendChild(info);

    // 这一列是"我们第一次同步到他"的日期,不是 GitHub 的原始关注时间(接口不返回)
    if (u.first_seen) row.appendChild(h("span", "follow-date", u.first_seen.slice(0, 10)));
    listEl.appendChild(row);
  });
}

async function renderSearchDiscover() {
  listEl.replaceChildren();

  const [trend, tags, starred] = await Promise.all([
    getJSON("/api/repos?sort=trending&limit=6").catch(() => ({ items: [] })),
    getJSON("/api/tags?limit=24").catch(() => ({ items: [] })),
    getJSON("/api/me/starred?limit=200").catch(() => ({ items: [] })),
  ]);

  if (tags.items && tags.items.length) {
    const s = h("div", "section");
    s.appendChild(h("div", "section-title", t("discover_tags")));
    const cloud = h("div", "topics");
    cloud.style.marginTop = "0";
    tags.items.forEach(item => {
      const chip = h("span", "topic clickable", `${item.tag} ${item.n}`);
      chip.onclick = () => toggleTag(item.tag);
      cloud.appendChild(chip);
    });
    s.appendChild(cloud);
    listEl.appendChild(s);
  }

  if (trend.items && trend.items.length) {
    const s = h("div", "section");
    s.appendChild(h("div", "section-title", t("discover_trending")));
    trend.items.forEach(r => s.appendChild(repoPost(r, { feedback: true })));
    listEl.appendChild(s);
  }

  const auth = authorsSection(starred.items);
  if (auth) listEl.appendChild(auth);

  statusEl.textContent = listEl.children.length ? "" : t("discover_empty");
}

// ---- 详情 ----
function renderDetail(d) {
  detailEl.replaceChildren();
  listEl.replaceChildren();
  searchPageEl.style.display = "none";
  searchPageEl.replaceChildren();
  statusEl.textContent = "";
  toolbarEl.replaceChildren();
  titleEl.textContent = d.full_name;
  pageBackEl.title = t("back");
  showPageBack(true);                 // 详情页才显示返回按钮
  detailEl.style.display = "block";

  // 不再放"返回"按钮 —— 路由化之后浏览器后退键就是返回,页面里再放一个是重复。
  const head = h("div", "detail-head");

  // 作者头像本身就是链接,点它直接去作者的 GitHub 主页
  const owner = ownerOf(d.full_name);
  const avLink = h("a", "avatar-link");
  avLink.href = "https://github.com/" + owner;
  avLink.target = "_blank";
  avLink.rel = "noopener noreferrer";
  avLink.title = owner;
  avLink.appendChild(avatarImg(owner, 112));
  head.appendChild(avLink);

  // 标题本身就是去 GitHub 的链接(返回按钮在页头,不在这儿了)
  const titleLink = h("a", "detail-title", d.full_name);
  titleLink.href = d.html_url || ("https://github.com/" + d.full_name);
  titleLink.target = "_blank";
  titleLink.rel = "noopener noreferrer";
  titleLink.title = t("open_github");
  head.appendChild(titleLink);

  // "在 GitHub 打开" 的按钮去掉了 —— 标题本身就是那个链接,不用两个入口做同一件事

  // Releases 页面链接
  const rel = h("a", "btn", t("releases") + " ↗");
  rel.href = d.releases_url || ((d.html_url || "").replace(/\/$/, "") + "/releases");
  rel.target = "_blank";
  rel.rel = "noopener noreferrer";
  head.appendChild(rel);
  detailEl.appendChild(head);

  if (d.description) detailEl.appendChild(h("p", "detail-desc", d.description));

  const meta = h("div", "detail-meta");
  meta.appendChild(ownerLink(ownerOf(d.full_name)));
  if (d.language) meta.appendChild(h("span", null, d.language));
  // 星数不在这儿显示 —— 下面操作行的星图标已经带数量了
  if (d.delta !== null && d.delta !== undefined) {
    meta.appendChild(h("span", "delta", t("delta_recent") + " " + d.delta));
  }
  if (d.pushed_at) meta.appendChild(h("span", null, t("last_push") + " " + d.pushed_at.slice(0, 10)));
  if (d.starred_at) meta.appendChild(h("span", null, t("starred_at") + " " + d.starred_at.slice(0, 10)));
  detailEl.appendChild(meta);

  if (d.topics && d.topics.length) {
    const box = h("div", "topics");
    d.topics.forEach(tag => {
      const on = state.tags.includes(tag);
      const chip = h("span", "topic clickable" + (on ? " on" : ""), tag);
      chip.title = on ? t("tag_remove") : t("tag_add");
      chip.onclick = () => toggleTag(tag);
      box.appendChild(chip);
    });
    detailEl.appendChild(box);
  }

  // 三个点放到页头 "Releases" 的右边
  detailEl.appendChild(postActions(d, detailEl, { moreHost: head }));

  // 笔记:能写、能看
  const cs = h("div", "section");
  const csTitle = h("div", "section-title", t("comments", (d.comments || []).length));
  cs.appendChild(csTitle);

  const ta = document.createElement("textarea");
  ta.className = "comment-input";
  ta.rows = 3;
  ta.placeholder = t("comment_placeholder");

  const send = h("button", "btn primary", t("comment_send"));
  const cnote = h("span", "muted");
  const clist = h("div", "comment-list");

  const paintComments = (items) => {
    clist.replaceChildren();
    csTitle.textContent = t("comments", (items || []).length);
    if (!items || !items.length) {
      clist.appendChild(h("p", "muted", t("comment_none")));
      return;
    }
    items.forEach(c => {
      const row = h("div", "comment");
      // 评论者:从 users 表关联出来的(不是存的字符串)—— 这正是多用户的意义
      const meta = h("div", "comment-meta");
      if (c.author_login) meta.appendChild(avatarImg(c.author_login, 32));
      meta.appendChild(h("span", null,
        (c.author_login || t("me")) + " · " +
        (c.created_at || "").slice(0, 16).replace("T", " ")));
      row.appendChild(meta);
      row.appendChild(h("div", "comment-body", c.body));
      clist.appendChild(row);
    });
  };
  paintComments(d.comments);

  send.onclick = async () => {
    const text = ta.value.trim();
    if (!text) return;
    send.disabled = true;
    cnote.textContent = "";
    try {
      const res = await fetch(API + "/api/comments/" + d.full_name, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: text }),
      });
      const out = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(out.detail || ("HTTP " + res.status));
      ta.value = "";
      paintComments(out.items);
    } catch (e) {
      cnote.textContent = t("comment_fail") + e.message;
    } finally {
      send.disabled = false;
    }
  };

  // 没登录就不给写 —— 评论是要署名的,总得知道是谁写的
  if (currentUser.logged_in) {
    const editor = h("div", "comment-editor");
    editor.appendChild(ta);
    const row = h("div", "comment-actions");
    row.appendChild(send);
    row.appendChild(cnote);
    editor.appendChild(row);
    cs.appendChild(editor);
  } else {
    const a = h("a", "btn", t("login"));
    a.href = API + "/auth/login";
    cs.appendChild(a);
  }
  cs.appendChild(clist);
  detailEl.appendChild(cs);

  // 从"评论数"按钮点进来的,滚到评论区
  if (scrollTo === "comments") {
    scrollTo = null;              // 只滚一次
    cs.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // 介绍只留一处。之前标题下面一个 description、下面又有一个"介绍" section,
  // 两段意思差不多的话摞在一起。
  // 保留 description —— 它是仓库自己写的,一定准确;README 抽出来的那段是启发式的,
  // 而且详情页下面就有 README 全文,再摘一段反而多余。
  if (d.history && d.history.length) {
    const s = h("div", "section");
    s.appendChild(h("div", "section-title", t("snapshots", d.history.length)));
    const chart = h("div", "chart");
    const vals = d.history.map(x => x.stargazers_count);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    d.history.forEach(x => {
      const col = h("div", "chart-col");
      const bar = h("div", "chart-bar");
      const ratio = hi > lo ? (x.stargazers_count - lo) / (hi - lo) : 0.5;
      bar.style.height = (12 + ratio * 60) + "px";
      bar.title = `${x.snapshot_date}: ${x.stargazers_count}`;
      col.appendChild(bar);
      col.appendChild(h("span", "chart-label", x.snapshot_date.slice(5)));
      chart.appendChild(col);
    });
    s.appendChild(chart);
    detailEl.appendChild(s);
  }

  const rs = h("div", "section");
  const rhead = h("div", "section-head");
  rhead.appendChild(h("div", "section-title", t("readme")));
  rs.appendChild(rhead);
  if (d.readme && d.readme.trim()) {
    const pre = h("pre", "readme");
    pre.textContent = d.readme;
    // README 也能翻译。它比介绍长得多,后端会分块翻,所以会等一会儿。
    // 按钮放在标题行而不是正文里 —— 正文是可滚动区域,放里面会跟着滚走。
    rhead.appendChild(translateButton(() => pre.textContent,
                                     (s) => { pre.textContent = s; }));
    rs.appendChild(pre);
  } else {
    rs.appendChild(h("p", "muted", t("readme_none")));
  }
  detailEl.appendChild(rs);

  if (d.similar && d.similar.length) {
    const s = h("div", "section");
    s.appendChild(h("div", "section-title", t("similar")));
    d.similar.forEach(x => {
      const r2 = h("div", "similar-row");
      const a = h("a", "name", x.full_name);
      a.href = "#/repo/" + x.full_name;
      a.onclick = (e) => { e.preventDefault(); navigate("#/repo/" + x.full_name); };
      r2.appendChild(a);
      // 相似度可能没有(比如探索位就不带这个字段)。
      // 直接 .toFixed() 的话,哪天后端少给一个字段,整个详情页就白了 ——
      // 而且是 TypeError,不是"少显示一行"。缺了就少显示一段,别让页面挂掉。
      const sim = (x.similarity === undefined || x.similarity === null)
        ? "" : ` · ${x.similarity.toFixed(3)}`;
      r2.appendChild(h("span", "muted",
        `  ${x.language || "?"} · ★${nfmt(x.stargazers_count)}${sim}`));
      s.appendChild(r2);
    });
    detailEl.appendChild(s);
  }
}

// 详情请求的"代次"计数器:每打开一个仓库就 +1。
// 响应回来时如果已经不是自己那一代,说明用户早切走了 —— 直接丢掉,别画。
//
// 不加这个会渲染错内容:先点 A 再快速点 B(或连按后退键切来切去),
// 只要 A 的响应晚于 B 返回,A 就会覆盖 B 的页面 ——
// 地址栏和标题写着 B,正文和点赞状态却是 A。
//
// 这个窗口**不小**:后端碰到"还没抓过 README"的仓库会**现场去 GitHub 拉一次**
// (见 api.py 的按需抓取),那一下可能要好几秒。
let detailSeq = 0;

async function showDetail(fullName) {
  const seq = ++detailSeq;
  detailEl.style.display = "block";
  detailEl.replaceChildren();
  listEl.replaceChildren();
  searchPageEl.style.display = "none";
  statusEl.textContent = t("loading");
  toolbarEl.replaceChildren();

  try {
    const op = await getJSON("/api/opinions");
    const repo = await getJSON("/api/repos/" + fullName);
    if (seq !== detailSeq) return;      // 用户已经切到别的仓库了,这次的结果作废
    opinions = op.opinions || {};
    renderDetail(repo);
  } catch (e) {
    if (seq !== detailSeq) return;      // 过期的错误也不该盖住新页面
    detailEl.replaceChildren();
    if (!needLogin(e)) statusEl.textContent = t("detail_error") + e.message;
  }
}

function render(items, opts) {
  listEl.replaceChildren();
  if (!items.length) {
    statusEl.textContent = opts.empty || t("no_data");
    return;
  }
  items.forEach(r => listEl.appendChild(repoPost(r, opts)));
  statusEl.textContent = opts.summary || "";
}

// ---- 推荐页:滚到底自动加载下一批 ----
// 像 Google 那样滑到底就自动出下一页,**追加**在后面而不是替换。
// 好处:不用手动点按钮,而且翻过的内容不会"翻过去就没了"。
let loadingMore = false;
let moreSentinel = null;

// 列表末尾那个"哨兵"。滚动监听到它快进视野了就再拉一批。
// hasMore 由调用方给 —— 推荐页和兔子洞各有各的"还有没有更多"。
function appendMoreSentinel(hasMore) {
  moreSentinel = h("div", "more-sentinel muted",
                   hasMore ? "" : t("list_end"));
  listEl.appendChild(moreSentinel);
}

async function loadMoreRecommend() {
  if (loadingMore || !state.hasMore || state.tab !== "recommend" || !moreSentinel) return;
  loadingMore = true;

  // 把"这一次请求"绑定的东西先抓在手里,后面判断是否已经过期要用。
  const sentinel = moreSentinel;
  const offset = state.offset;
  sentinel.textContent = t("loading");

  try {
    const d = await getJSON(
      `/api/recommend?limit=${PAGE}&offset=${offset}` +
      `&sort=${encodeURIComponent(state.sort)}`);

    // ⚠️ await 之后,世界可能已经变了 —— 用户在等的这几百毫秒里
    // 切了 tab、改了排序、按了浏览器后退。上一个页面发出去的请求,
    // 结果绝不能往当前页面上写。
    //
    // 不拦会有两个后果,都很隐蔽:
    //   · 换了页面 → 哨兵已经被 replaceChildren 摘掉,
    //     insertBefore 抛 NotFoundError,被下面 catch 到还会把新页面的状态行
    //     覆盖成一句"出错了"
    //   · 又切回推荐页 → 新哨兵已经建好,旧请求的数据被插进新列表
    //     (用的是旧的排序、旧的 offset),而且 state.offset 被旧值覆盖,
    //     后面翻页会重复或漏掉内容
    //
    // 三道判断:还在推荐页吗?哨兵还是我这一根吗?它还挂在文档里吗?
    if (state.tab !== "recommend" || moreSentinel !== sentinel ||
        !sentinel.isConnected) return;

    state.offset = d.offset + d.count;
    state.hasMore = d.has_more;
    // 插到"哨兵"前面 —— 这样哨兵始终在列表最末尾
    d.items.forEach(r =>
      listEl.insertBefore(repoPost(r, { feedback: true }), sentinel));
    sentinel.textContent = d.has_more ? "" : t("list_end");
    statusEl.textContent = t("summary_recommend", state.offset);
  } catch (e) {
    if (!needLogin(e)) statusEl.textContent = t("error") + e.message;
  } finally {
    loadingMore = false;
  }
}

// 离底部还有 700px 就提前开始加载 —— 等真到底了再加载,用户会看到一段空白
window.addEventListener("scroll", () => {
  if (loadingMore) return;
  const nearBottom = window.innerHeight + window.scrollY >=
                     document.documentElement.scrollHeight - 700;
  if (!nearBottom) return;
  // 两个页面都有"下滑加载更多",各自判断自己还有没有下一批
  if (state.tab === "recommend" && state.hasMore) {
    loadMoreRecommend();
  } else if (state.tab === "acg" && state.acgSub === "list" && state.acgHasMore) {
    loadMoreAcg();
  }
});

async function getJSON(path) {
  const res = await fetch(API + path, FETCH_OPTS);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(body.detail || ("HTTP " + res.status));
    err.status = res.status;
    throw err;
  }
  return body;
}

// 需要登录的页面:没登录就显示一个登录提示,而不是一句干巴巴的错误
function needLogin(err) {
  if (err && err.status === 401) {
    showLoginPrompt();
    return true;
  }
  return false;
}

// ---- 右上角的用户菜单 ----
const userMenuEl = document.getElementById("usermenu");

// token 失效的提示条。
//
// 为什么值得专门占一块地方:token 失效是**完全静默**的 ——
// 页面照常打开、推荐照常显示(用的都是旧数据),唯一的区别是
// "你新 star 的仓库不会再被同步进来"。不主动说,用户只会以为这站坏了,
// 不会想到是自己需要重新登录一次。
//
// 状态来自 /api/me 的 user.token_ok —— 每日同步时更新(见 sync_all.py)。
function renderTokenWarning() {
  const bad = currentUser.logged_in && currentUser.user &&
              currentUser.user.token_ok === false;
  tokenWarnEl.replaceChildren();
  if (!bad) {
    tokenWarnEl.style.display = "none";
    return;
  }
  tokenWarnEl.appendChild(h("span", "grow", t("token_bad")));
  const a = h("a", null, t("token_bad_go"));
  // 直接指到 /auth/login:走一遍 GitHub 授权就换了新 token,
  // 并把 token_ok 重置回 1(见 db.upsert_user)。**不用先退出登录。**
  a.href = "/auth/login";
  tokenWarnEl.appendChild(a);
  tokenWarnEl.style.display = "flex";
}

// 星标之类的操作失败后,顺手重问一次"我是谁"。
//
// 为什么需要:后端在发现 token 失效时会把它记进库(见 api.py 的 /api/star),
// 但那是**服务端**的状态,页面不会自己知道。重问一次 /api/me,
// 顶部那条提示就能立刻出现 —— 而不是等用户下次刷新页面才看到。
async function refreshTokenWarning() {
  const me = await getJSON("/api/me").catch(() => null);
  if (!me) return;
  currentUser = me;
  renderTokenWarning();
}

async function renderUserMenu() {
  userMenuEl.replaceChildren();

  let me = { logged_in: false };
  try {
    me = await getJSON("/api/me");
  } catch { /* 拿不到就当没登录,不弹错 */ }
  currentUser = me;               // 别处(比如评论区)也要知道登录没登录

  if (!me.logged_in) {
    const a = h("a", "btn", t("login"));
    a.href = API + "/auth/login";
    if (!me.oauth_ready) a.title = t("login_not_ready");
    userMenuEl.appendChild(a);
    return;
  }

  const wrap = h("div", "sel more user");
  const btn = h("button", "icon-btn avatar-btn");
  btn.title = me.user.login;
  if (me.user.avatar_url) {
    const img = document.createElement("img");
    img.className = "avatar";
    img.src = me.user.avatar_url;
    img.alt = me.user.login;
    img.referrerPolicy = "no-referrer";
    img.onerror = () => { img.removeAttribute("src"); };
    btn.appendChild(img);
  } else {
    btn.appendChild(iconSpan("user", 22));
  }
  wrap.appendChild(btn);

  const menu = h("div", "sel-menu");
  const addItem = (iconKey, labelText, onClick) => {
    const item = h("div", "sel-item");
    item.appendChild(iconSpan(iconKey, 16));
    item.appendChild(h("span", null, labelText));
    item.onclick = (e) => {
      e.stopPropagation();
      wrap.classList.remove("open");
      onClick();
    };
    menu.appendChild(item);
  };

  // 手机上的底部条只放 5 个主入口,其余的(已关注/刷新/外观/语言)都收在这儿。
  // 桌面上这些在左侧导航里也有 —— 重复但无害,而且当快捷入口挺方便。
  addItem("user", t("tab_following"), () => navigate("#/following"));

  // 手机上不给"刷新":手机本来就能下拉刷新页面,菜单里再来一个纯属多余。
  // 桌面上留着,因为左侧竖栏虽然也有,但走菜单更快。
  if (window.innerWidth > 700) {
    addItem("refresh", t("refresh"), () => loadList());
  }

  const theme = currentTheme();
  addItem(theme === "light" ? "sun" : "moon",
          t(theme === "light" ? "theme_light" : "theme_dark"),
          () => {
            const next = theme === "light" ? "dark" : "light";
            localStorage.setItem("theme", next);
            applyTheme(next);
            buildRail();
            renderUserMenu();
          });

  addItem("globe", t(lang === "zh" ? "lang_zh" : "lang_en"), () => {
    lang = lang === "zh" ? "en" : "zh";
    localStorage.setItem("ui_lang", lang);
    buildRail();
    renderNavMenu();
    renderUserMenu();
    route();
  });

  addItem("logout", t("logout"), async () => {
    try {
      await fetch(API + "/auth/logout", { method: "POST", credentials: "include" });
    } catch { /* 退出失败也照常走 */ }
    location.reload();          // 重新走一遍启动流程 —— 会停在登录页
  });

  wrap.appendChild(menu);

  btn.onclick = (e) => {
    e.stopPropagation();
    const wasOpen = wrap.classList.contains("open");
    document.querySelectorAll(".sel.open").forEach(s => s.classList.remove("open"));
    if (!wasOpen) wrap.classList.add("open");
  };
  userMenuEl.appendChild(wrap);
}

// 没登录时:整页只有登录界面,而不是进主页面再到处报错
function renderLoginScreen(me) {
  document.body.classList.add("logged-out");   // 导航不显示,内容也不用给它让位
  railEl.replaceChildren();
  const head = document.querySelector(".pagehead");
  if (head) head.style.display = "none";
  toolbarEl.replaceChildren();
  listEl.replaceChildren();
  searchPageEl.style.display = "none";
  detailEl.style.display = "none";
  statusEl.textContent = "";

  const box = h("div", "login-screen");
  const brand = h("div", "login-brand");
  const ico = h("span", "ico");
  ico.innerHTML = ICONS.brand;
  brand.appendChild(ico);
  brand.appendChild(h("span", null, APP_NAME));
  box.appendChild(brand);

  box.appendChild(h("p", "login-blurb", t("login_blurb")));

  const a = h("a", "btn primary", t("login"));
  a.href = API + "/auth/login";
  box.appendChild(a);

  if (!me.oauth_ready) {
    box.appendChild(h("p", "muted", t("login_not_ready")));
  }
  listEl.appendChild(box);
}

// ---- 标题旁边的导航下拉(手机上用)----
// 手机上不显示左侧竖栏,把这个下拉放在大标题右边代替它。
// 大屏幕上它是隐藏的 —— 那边有竖栏,不需要再来一个。
const navMenuEl = document.getElementById("navmenu");

function renderNavMenu() {
  navMenuEl.replaceChildren();

  const wrap = h("div", "sel more");
  const btn = h("button", "icon-btn");
  btn.title = t("menu");
  btn.appendChild(iconSpan("chevronDown", 22));
  wrap.appendChild(btn);

  const menu = h("div", "sel-menu");
  NAV.forEach(([tab, labelKey, iconKey]) => {
    const item = h("div", "sel-item");
    item.appendChild(iconSpan(iconKey, 16));
    item.appendChild(h("span", null, t(labelKey)));
    item.onclick = (e) => {
      e.stopPropagation();
      wrap.classList.remove("open");
      navigate("#/" + tab);
    };
    menu.appendChild(item);
  });
  wrap.appendChild(menu);

  btn.onclick = (e) => {
    e.stopPropagation();
    const wasOpen = wrap.classList.contains("open");
    document.querySelectorAll(".sel.open").forEach(s => s.classList.remove("open"));
    if (!wasOpen) wrap.classList.add("open");
  };
  navMenuEl.appendChild(wrap);
}

function showLoginPrompt() {
  renderLoginScreen({ logged_in: false, oauth_ready: true });
}

// 渲染"列表类"页面(推荐 / Trending / 标签 / 我的 / 搜索)
async function loadList() {
  // ⚠️ 详情页不归这个函数管,拦在源头。
  //
  // 它下面那条 if 链只覆盖"列表类"页面,最后的 else 是"已收藏"。
  // 所以在详情页误调它(比如点刷新),会掉进 else ——
  // 整页被换成 star 列表;同时 setTitle 拼出 "tab_detail",
  // I18N 里没这个 key、t() 原样返回,页头就直接显示这串原始 key。
  // 而地址栏还停在 #/repo/... ,页面和 URL 对不上,后退键也跟着乱。
  //
  // 交给 route() 重走一遍:它就是"按当前 URL 重新渲染"的唯一入口。
  if (state.tab === "detail") return route();

  // 分站皮肤:只有列表页会切它。详情页走的是 showDetail,不经过这里 ——
  // 所以从分站点进仓库时,配色会一直保持,不会"进去就变回主站"。
  syncZone(state.tab);

  showPageBack(false);                // 列表页不需要返回按钮
  detailEl.style.display = "none";
  detailEl.replaceChildren();
  searchPageEl.style.display = "none";
  searchPageEl.replaceChildren();
  listEl.replaceChildren();
  toolbarEl.replaceChildren();
  statusEl.textContent = t("loading");
  setTitle(state.tab === "tag" ? "tab_tags"
           : state.tab === "acg" ? acgSubKeyForHash()
           : "tab_" + state.tab);

  try {
    const op = await getJSON("/api/opinions");
    opinions = op.opinions || {};

    if (state.tab === "search") {
      statusEl.textContent = "";
      searchPageEl.style.display = "block";
      searchPageEl.appendChild(searchBar());
      if (!state.q) {
        await renderSearchDiscover();
        return;
      }
      renderToolbar();
      const p = new URLSearchParams({ q: state.q, limit: 60, scope: state.scope,
                                      sort: state.searchSort });
      const d = await getJSON("/api/search?" + p.toString());
      render(d.items, {
        feedback: true,
        summary: t(d.scope === "github" ? "summary_search_github" : "summary_search", d.q, d.count),
        empty: t("search_empty"),
      });
      return;
    }

    renderToolbar();

    if (state.tab === "trending" || state.tab === "tag") {
      const p = new URLSearchParams({ sort: state.sort, limit: 30 });
      state.tags.forEach(x => p.append("tag", x));
      const d = await getJSON("/api/repos?" + p.toString());
      let summary;
      if (state.tags.length) {
        summary = t("summary_tags", state.tags.join(" "), d.count, t("sort_" + state.sort));
      } else if (d.sort === "trending") {
        summary = t("summary_trending", d.since, d.as_of, d.count);
      } else {
        summary = t("summary_sorted", t("sort_" + d.sort), d.count);
      }
      render(d.items, {
        feedback: true, summary,
        empty: state.tags.length ? t("tag_empty") : undefined,
      });
    } else if (state.tab === "recommend") {
      // 第一批。后面靠滚到底自动加载(loadMoreRecommend),不再有"换一批"
      const d = await getJSON(
        `/api/recommend?limit=${PAGE}&offset=0&sort=${encodeURIComponent(state.sort)}`);
      state.offset = d.count;
      state.hasMore = d.has_more;
      listEl.replaceChildren();
      d.items.forEach(r => listEl.appendChild(repoPost(r, { feedback: true })));
      appendMoreSentinel(state.hasMore);
      statusEl.textContent = t("summary_recommend", d.count);
    } else if (state.tab === "tags") {
      // q 交给后端筛(见 /api/tags)—— 前端筛的话,落在 LIMIT 之外的冷门标签
      // 永远搜不到,而且看不出是为什么
      const p = new URLSearchParams({ limit: 200 });
      if (state.tagQ) p.set("q", state.tagQ);
      renderTagCloud(await getJSON("/api/tags?" + p.toString()));
    } else if (state.tab === "following") {
      await renderFollowing();
    } else if (state.tab === "acg") {
      // 洞里有两个子页。靠 state.acgSub 分,它来自 URL
      // (路由那层已经把 `#/acg/tags` 解析成 acgSub="tags" 了)。
      await (state.acgSub === "tags" ? renderAcgTags() : renderAcg());
    } else {
      // 已收藏:你 star 过的仓库。两种看法(顶部切换):
      //   list   卡片列表,和别处一样
      //   status 它们"现在怎么样了" —— 还在更新吗、还在涨吗
      if (state.starredView === "status") {
        await renderStarredStatus();
      } else {
        const d = await getJSON("/api/me/starred?limit=200");
        render(d.items, { feedback: false, summary: t("summary_starred", d.count) });
      }
    }
  } catch (e) {
    if (!needLogin(e)) statusEl.textContent = t("error") + e.message;
  }
}

// 启动
applyTheme(currentTheme());
syncRailOpen();
window.addEventListener("resize", syncRailOpen);   // 拖窗口大小时跟着变
document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";

// 页面标题在这里**同步**设好,不放进下面那个异步流程。
// 原因:异步流程要等 /api/me 回来(几百毫秒),那段时间里页面会先显示
// HTML 里的初始值,再跳成正确的标题 —— 看起来像"先 Trending,然后才变成为你推荐"。
// 标题只依赖 URL,现在就能算出来,没必要等。
// 兔子洞首页的标题。**它是写死的装饰文案,不走 i18n** ——
// 它是一句"欢迎来到…"的话,不是一个界面标签,没有翻译的必要。
// (t() 找不到 key 时会原样返回,所以它和真正的 key 能混着用 ——
//  但看代码的人容易以为这是漏翻的,所以单独提出来放这儿。)
//
// 日文用「うさぎのあなへようこそ」,三点说明:
//   · 「へようこそ」是"欢迎来到"的固定说法。「にようこそ」也通,但少见。
//   · 「うさぎ」写假名,不写汉字「兎」—— 兎 不在日本常用汉字表里,
//     现代日语里兔子基本都写假名;写成 兎 会显得偏书面、老气。
//   · ⚠️ **「あな」也必须写假名,不能用汉字「穴」。**
//     页面标题用的 Donguriko 免费版**只收录平假名和标点,一个汉字都没有**
//     (收费版才有 248 个汉字)。写成 穴 的话,那一个字会掉回系统字体 ——
//     整句里只有它长得不一样,这比整体不好看更难查。
//     换字体时记得回来看一眼这条:不同字体收录范围不一样。
const ACG_TITLE = "うさぎのあなへようこそ！";

// 洞里有两个子页,标题得跟着分 —— 不然标签云页顶上写着"兔子洞",
// 看着像没切过去。这个也是**同步**算的(标题不能等异步流程)。
function acgSubKeyForHash() {
  const parts = location.hash.replace(/^#\/?/, "").split("?")[0]
    .split("/").filter(Boolean);
  return parts[1] === "tags" ? "acg_tags" : ACG_TITLE;
}

function titleKeyForHash() {
  const head = (location.hash.replace(/^#\/?/, "").split("?")[0]
    .split("/").filter(Boolean)[0]) || "recommend";
  if (head === "repo") return null;        // 详情页标题是仓库名,那得等数据回来
  if (head === "tag") return "tab_tags";
  if (head === "acg") return acgSubKeyForHash();   // 洞里的子页标题不一样
  return "tab_" + (TABS.includes(head) ? head : "recommend");
}
const _initialTitle = titleKeyForHash();
if (_initialTitle) titleEl.textContent = t(_initialTitle);

(async () => {
  // 先问一句"我是谁":**没登录就直接停在登录页**,不要先闪一下主界面再到处报错
  const me = await getJSON("/api/me").catch(() => ({ logged_in: false }));
  currentUser = me;
  if (!me.logged_in) {
    renderLoginScreen(me);
    return;
  }
  buildRail();
  renderNavMenu();          // 手机上的导航下拉(大屏幕下 CSS 会把它藏起来)
  // 没有 hash 就补一个,并且用 replaceState —— 别让"进入网站"本身占用一条历史记录
  if (!location.hash) history.replaceState(null, "", "#/recommend");
  renderUserMenu();
  renderTokenWarning();     // token 失效就挂一条提示(状态来自这个 /api/me)
  route();
})();
