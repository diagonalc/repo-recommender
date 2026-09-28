// P8:前端逻辑。原生 JS,没有框架。
//
// 路由:用 hash(#/xxx)把"在看哪一页"放进 URL。
//   为什么用 hash 不用路径:静态服务器直接能用,刷新不会 404,不需要后端配合。
//   好处是**浏览器的前进/后退真的能用**,而不是只能点页面里那个"返回"。
//
// 导航:左侧竖栏(悬停展开)+ 中间窄栏内容。文案统一走 t("key"),中英可切;外观中英同理。
const API = "http://127.0.0.1:8000";

const I18N = {
  zh: {
    tab_trending: "Trending", tab_recommend: "为你推荐", tab_tags: "标签",
    tab_starred: "已收藏", tab_search: "搜索", tab_following: "已关注",
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
    sort_similarity: "相似度",
    refresh: "刷新", refresh_batch: "换一批",
    loading: "加载中…", no_data: "没有数据。", error: "出错了:",
    open_github: "在 GitHub 打开", releases: "Releases", back: "返回上一页",
    prev_batch: "上一批",
    interested: "感兴趣", not_interested: "不感兴趣", fail: "失败:",
    more: "更多", copy_link: "复制链接", copied: "已复制链接",
    un_not_interested: "取消不感兴趣",
    comments_go: "查看评论", star_go: "在 GitHub 上 star", starred_ok: "已 star ✓",
    me: "我",
    snapshots: "star 快照 ({0})", readme: "README",
    readme_none: "还没抓到这个 repo 的 README。",
    similar: "相似的 repo", similarity: "相似度",
    comments: "评论 ({0})", comment_placeholder: "写下你的评论…",
    comment_send: "发表", comment_none: "还没有评论。", comment_fail: "发表失败:",
    tag_remove: "点一下移除", tag_add: "点一下筛选",
    tag_empty: "没有同时带这些标签的 repo —— 点掉上面一个试试。",
    tagcloud_title: "{0} 个标签 · 覆盖 {1}/{2} 个 repo",
    summary_trending: "近两个快照日({0} → {1})增量 Top {2}",
    summary_sorted: "按{0} · {1} 个",
    summary_tags: "{1} 个(标签 {0} · 按{2})",
    summary_batch: "第 {0} 批 · {1} 个",
    summary_batch_end: "第 {0} 批(最后一批)· {1} 个",
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
  },
  en: {
    tab_trending: "Trending", tab_recommend: "For You", tab_tags: "Tags",
    tab_starred: "Starred", tab_search: "Search", tab_following: "Following",
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
    refresh: "Refresh", refresh_batch: "New batch",
    loading: "Loading…", no_data: "No data.", error: "Error:",
    open_github: "Open on GitHub", releases: "Releases", back: "Go back",
    prev_batch: "Previous batch",
    interested: "Interested", not_interested: "Not interested", fail: "Failed: ",
    more: "More", copy_link: "Copy link", copied: "Link copied",
    un_not_interested: "Undo not interested",
    comments_go: "View comments", star_go: "Star on GitHub", starred_ok: "Starred ✓",
    me: "me",
    snapshots: "Star snapshots ({0})", readme: "README",
    readme_none: "No README captured yet.",
    similar: "Similar repos", similarity: "similarity",
    comments: "Comments ({0})", comment_placeholder: "Write a comment…",
    comment_send: "Post", comment_none: "No comments yet.", comment_fail: "Failed: ",
    tag_remove: "Click to remove", tag_add: "Click to filter",
    tag_empty: "No repo has all of these tags — click one above to remove it.",
    tagcloud_title: "{0} tags · {1}/{2} repos",
    summary_trending: "Top {2} by growth ({0} → {1})",
    summary_sorted: "{0} · {1} repos",
    summary_tags: "{1} repos (tags {0} · {2})",
    summary_batch: "Batch {0} · {1} repos",
    summary_batch_end: "Batch {0} (last) · {1} repos",
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
  document.body.classList.toggle("rail-open", window.innerWidth >= avail - 8);
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
  brand:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linecap="round" stroke-linejoin="round">' +
    '<rect x="2.6" y="2.6" width="18.8" height="18.8" rx="5.6"/>' +
    '<path d="M7.2 8.6h9.6M7.2 12h9.6M7.2 15.4h5.6"/></svg>',
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
  arrowRight:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M4.5 12h14"/><polyline points="12.5 6 18.5 12 12.5 18"/></svg>',
  arrowLeft:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M19.5 12h-14"/><polyline points="11.5 6 5.5 12 11.5 18"/></svg>',
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

const APP_NAME = "Repos";     // 站名占位

const listEl = document.getElementById("list");
const statusEl = document.getElementById("status");
const detailEl = document.getElementById("detail");
const searchPageEl = document.getElementById("searchpage");
const toolbarEl = document.getElementById("toolbar");
const railEl = document.getElementById("rail");
const titleEl = document.getElementById("pagetitle");
const pageBackEl = document.getElementById("pageback");

// 页头的返回按钮(只在详情页出现,在标题左边)
pageBackEl.appendChild(iconSpan("arrowLeft", 22));
pageBackEl.onclick = () => {
  if (history.length > 1) history.back();
  else navigate("#/recommend");
};

let opinions = {};
let scrollTo = null;   // 详情页渲染完后要滚到哪(从评论按钮进来时用)

// 只放"不进 URL"的界面状态。页面 / 标签 / 搜索词都从 URL 读,URL 是唯一事实来源。
const state = {
  tab: "recommend",
  sort: "similarity",
  tags: [],
  offset: 0,
  hasMore: true,
  q: "",
  scope: "local",
  returnTab: "trending",
  followQ: "",              // 已关注页的搜索词(只搜已关注的人)
  followSort: "name",       // name | recent | oldest
};
const PAGE = 30;
const SORTS = ["trending", "stars", "pushed", "name"];
const RECOMMEND_SORTS = ["similarity", "stars", "name"];
const TABS = ["trending", "recommend", "tags", "starred", "search", "following"];
const sortsFor = (tab) => (tab === "recommend" ? RECOMMEND_SORTS : SORTS);

const NAV = [
  ["recommend", "tab_recommend", "spark"],
  ["trending", "tab_trending", "trending"],
  ["search", "tab_search", "search"],
  ["tags", "tab_tags", "tag"],
  ["starred", "tab_starred", "star"],
  ["following", "tab_following", "user"],
];

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

function avatarImg(owner, size) {
  const img = document.createElement("img");
  img.className = "avatar";
  img.src = "https://github.com/" + encodeURIComponent(owner) + ".png?size=" + size;
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

function route() {
  const { parts, qs } = currentRoute();
  const head = parts[0] || "recommend";

  // #/repo/owner/name ,可选 ?to=comments 表示进来后滚到评论区
  if (head === "repo" && parts.length >= 3) {
    state.tab = "detail";
    scrollTo = qs.get("to") || null;
    setActiveTab(null);
    showDetail(decodeURIComponent(parts[1]) + "/" + decodeURIComponent(parts[2]));
    return;
  }
  scrollTo = null;

  // #/tag/a,b
  if (head === "tag" && parts[1]) {
    state.tags = parts[1].split(",").map(decodeURIComponent).filter(Boolean);
    state.tab = "tag";
    setActiveTab(null);
    setTitle("tab_tags");
    loadList();
    return;
  }

  state.tags = [];
  state.tab = TABS.includes(head) ? head : "recommend";

  // 每个页面能排的字段不同。切页面时如果当前排序在这个页面不合法,就换成默认的 ——
  // 否则会把 "similarity"(推荐页专有的选项)发给 Trending,接口直接 422。
  // 这段逻辑在引入路由时被我弄丢了,表现就是"点 Trending 页面出错"。
  if (!sortsFor(state.tab).includes(state.sort)) {
    state.sort = state.tab === "recommend" ? "similarity" : "trending";
  }

  if (state.tab === "search") {
    state.q = qs.get("q") || "";
    state.scope = qs.get("scope") || "local";
  }

  // 推荐页的"第几批"也放进 URL。这样**浏览器后退键天然就能回上一批** ——
  // 不用专门再造一套"上一批"的状态和历史,后退键本来就是干这个的。
  state.offset = state.tab === "recommend"
    ? Math.max(0, parseInt(qs.get("offset") || "0", 10) || 0)
    : 0;
  setActiveTab(state.tab);
  loadList();
}

window.addEventListener("hashchange", route);

// ---- 竖导航 ----
function railButton(iconKey, label, onClick, tab) {
  const b = h("button", "rail-btn");
  if (tab) b.dataset.tab = tab;
  const ico = h("span", "ico");
  ico.innerHTML = ICONS[iconKey];      // 常量 SVG,没有外部输入
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
  bico.innerHTML = ICONS.brand;
  brand.appendChild(bico);
  brand.appendChild(h("span", "rail-label", APP_NAME));
  brand.onclick = () => navigate("#/recommend");
  railEl.appendChild(brand);

  NAV.forEach(([tab, labelKey, iconKey]) => {
    railEl.appendChild(railButton(iconKey, t(labelKey), () => navigate("#/" + tab), tab));
  });

  railEl.appendChild(h("div", "rail-spacer"));

  // 底部这个"刷新"就是单纯重新拉一次当前页面,不动批次
  railEl.appendChild(railButton("refresh", t("refresh"), () => loadList()));

  // 语言:显示**当前**语言(和外观按钮同一套逻辑 —— 显示现在是什么,不是点了会变成什么)
  railEl.appendChild(railButton("globe", t(lang === "zh" ? "lang_zh" : "lang_en"), () => {
    lang = lang === "zh" ? "en" : "zh";
    localStorage.setItem("ui_lang", lang);
    buildRail();
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
    state.returnTab = state.tab === "tag" ? "trending" : state.tab;
  }
  const next = state.tags.includes(tag)
    ? state.tags.filter(x => x !== tag)
    : state.tags.concat(tag);
  navigate(next.length ? tagHash(next) : "#/" + (state.returnTab || "trending"));
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
      const res = await fetch(API + "/api/star/" + r.full_name, { method: "POST" });
      const out = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(out.detail || ("HTTP " + res.status));
      st.classList.add("on");
      note.textContent = t("starred_ok");
    } catch (err) {
      note.textContent = err.message;      // 比如 token 没权限,把原话显示出来
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
  if (opts.reasonText) wrap.appendChild(note);
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

  if (state.tab === "recommend") {
    // 不在第一批时,给一个回上一批的入口(浏览器后退键也行)
    if (state.offset > 0) {
      const prev = h("button", "btn");
      prev.appendChild(iconSpan("arrowLeft", 15));
      prev.appendChild(h("span", null, t("prev_batch")));
      prev.onclick = () => {
        const o = Math.max(0, state.offset - PAGE);
        navigate(o ? "#/recommend?offset=" + o : "#/recommend");
      };
      toolbarEl.appendChild(prev);
    }

    const b = h("button", "btn");
    b.appendChild(iconSpan("refresh", 15));
    b.appendChild(h("span", null, t("refresh_batch")));
    // 走 navigate 而不是直接改 state —— 每换一批就是一条历史记录,
    // 后退键才能一步步退回去
    b.onclick = () => {
      const next = state.hasMore ? state.offset + PAGE : 0;
      navigate(next ? "#/recommend?offset=" + next : "#/recommend");
    };
    toolbarEl.appendChild(b);
  }

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
    input.className = "follow-search";
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
  const wrap = h("div");
  wrap.appendChild(h("div", "section-title",
    t("tagcloud_title", d.count, d.tagged_repos, d.total_repos)));
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
  statusEl.textContent = "";
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

    if (u.avatar_url) {
      const img = document.createElement("img");
      img.className = "avatar";
      img.src = u.avatar_url;
      img.alt = u.login;
      img.loading = "lazy";
      img.referrerPolicy = "no-referrer";
      img.onerror = () => { img.removeAttribute("src"); };
      row.appendChild(img);
    } else {
      row.appendChild(avatarImg(u.login, 88));
    }

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
      // 作者:现在只有你自己,所以库里是空的,显示成"我"。
      // 以后多人用的时候,这一列就有名字了。
      row.appendChild(h("div", "comment-meta",
        (c.author || t("me")) + " · " +
        (c.created_at || "").slice(0, 16).replace("T", " ")));
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

  const editor = h("div", "comment-editor");
  editor.appendChild(ta);
  const row = h("div", "comment-actions");
  row.appendChild(send);
  row.appendChild(cnote);
  editor.appendChild(row);
  cs.appendChild(editor);
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
      r2.appendChild(h("span", "muted",
        `  ${x.language || "?"} · ★${nfmt(x.stargazers_count)} · ${x.similarity.toFixed(3)}`));
      s.appendChild(r2);
    });
    detailEl.appendChild(s);
  }
}

async function showDetail(fullName) {
  detailEl.style.display = "block";
  detailEl.replaceChildren();
  listEl.replaceChildren();
  searchPageEl.style.display = "none";
  statusEl.textContent = t("loading");
  toolbarEl.replaceChildren();

  try {
    const op = await getJSON("/api/opinions");
    opinions = op.opinions || {};
    renderDetail(await getJSON("/api/repos/" + fullName));
  } catch (e) {
    detailEl.replaceChildren();
    statusEl.textContent = t("detail_error") + e.message;
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

async function getJSON(path) {
  const res = await fetch(API + path);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || ("HTTP " + res.status));
  return body;
}

function sortRecommend(items) {
  const copy = items.slice();
  if (state.sort === "stars") copy.sort((a, b) => b.stargazers_count - a.stargazers_count);
  else if (state.sort === "name") copy.sort((a, b) => a.full_name.localeCompare(b.full_name));
  return copy;   // "similarity" = 服务端原序
}

// 渲染"列表类"页面(推荐 / Trending / 标签 / 我的 / 搜索)
async function loadList() {
  showPageBack(false);                // 列表页不需要返回按钮
  detailEl.style.display = "none";
  detailEl.replaceChildren();
  searchPageEl.style.display = "none";
  searchPageEl.replaceChildren();
  listEl.replaceChildren();
  toolbarEl.replaceChildren();
  statusEl.textContent = t("loading");
  setTitle(state.tab === "tag" ? "tab_tags" : "tab_" + state.tab);

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
      const p = new URLSearchParams({ q: state.q, limit: 60, scope: state.scope });
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
      const d = await getJSON(`/api/recommend?limit=${PAGE}&offset=${state.offset}`);
      state.hasMore = d.has_more;
      const batch = Math.floor(d.offset / PAGE) + 1;
      render(sortRecommend(d.items), {
        feedback: true,
        summary: t(d.has_more ? "summary_batch" : "summary_batch_end", batch, d.items.length),
      });
    } else if (state.tab === "tags") {
      renderTagCloud(await getJSON("/api/tags?limit=200"));
    } else if (state.tab === "following") {
      await renderFollowing();
    } else {
      // 已收藏:你 star 过的仓库
      // (原来这里顶上还挂了个"你 star 过的作者",现在拆出独立的"已关注"页了,
      //  那栏是用 star 反推的,和真实的关注列表摆在一起会让人分不清,所以去掉)
      const d = await getJSON("/api/me/starred?limit=200");
      render(d.items, { feedback: false, summary: t("summary_starred", d.count) });
    }
  } catch (e) {
    statusEl.textContent = t("error") + e.message;
  }
}

// 启动
applyTheme(currentTheme());
syncRailOpen();
window.addEventListener("resize", syncRailOpen);   // 拖窗口大小时跟着变
document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
buildRail();
// 没有 hash 就先补一个,并且用 replaceState —— 别让"进入网站"这件事本身占用一条历史记录
if (!location.hash) history.replaceState(null, "", "#/recommend");
route();
