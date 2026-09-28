// P8:前端逻辑。原生 JS,没有框架。
//
// 视图:
//   列表   Trending / 推荐 / 标签 / 我的 / 搜索
//   标签   点卡片上的标签会"叠加"上去(每加一个收窄一次),点掉就移除
//   详情   点 repo 名字 → README 正文等
//
// 界面语言:中/英可切。所有文案都走 t("key"),不写死在代码里 ——
// 否则加一种语言就得满文件找字符串,迟早漏掉几个。
const API = "http://127.0.0.1:8000";

const I18N = {
  zh: {
    tab_trending: "Trending", tab_recommend: "推荐", tab_tags: "标签", tab_starred: "我的",
    sort_label: "排序:",
    sort_trending: "最近增量", sort_stars: "总星数", sort_pushed: "最近更新", sort_name: "名称",
    refresh: "↻ 刷新", refresh_batch: "↻ 换一批", loading_more: "↻ 读取中…",
    batch_hint: "每批 30 个,下一批都是没看过的",
    loading: "加载中…", no_data: "没有数据。", error: "出错了:",
    open_github: "在 GitHub 打开 ↗", back: "← 返回列表",
    interested: "感兴趣", not_interested: "不感兴趣",
    chosen_interested: "✓ 已选:感兴趣", chosen_not: "✓ 已选:不感兴趣",
    already: "(已经是这个了)", recording: "记录中…",
    recorded: "(已记录,回列表看推荐变化)", change_hint: "(再点另一个可以改)",
    fail: "失败:", author: "作者 ", intro_label: "介绍:",
    one_line: "一句话介绍", snapshots: "star 快照({0} 次)", readme: "README 正文",
    similar: "相似的 repo", similarity: "相似度", no_readme: "库里还没抓到这个 repo 的 README。",
    tags_label: "标签:",
    tag_remove_hint: "点一下移除这个标签",
    tag_add_hint: "点一下叠加这个标签(每加一个收窄一次)",
    tag_empty: "没有同时带这些标签的 repo —— 点掉上面一个试试。",
    tagcloud_hint: "点任意标签,看带这个标签的 repo;进去后还能在卡片上继续点标签叠加",
    tagcloud_title: "{0} 个标签,覆盖 {1} / {2} 个 repo",
    summary_trending: "近两个快照日({0} → {1})star 增量 Top {2}",
    summary_sorted: "按{0}排序,共 {1} 个",
    summary_tags: "标签「{0}」下 {1} 个 repo(按{2})",
    summary_batch: "第 {0} 批推荐({1} 个)",
    batch_more: " · 点右上角 ↻ 换一批", batch_end: " · 已经是最后一批,再点 ↻ 回到第一批",
    summary_starred: "你 star 过的 {0} 个 repo(按 star 时间倒序)",
    summary_search: "搜「{0}」找到 {1} 个",
    search_empty: "没搜到匹配的 repo。",
    search_placeholder: "搜索 repo:名字 / 描述 / 标签 / README",
    scope_local: "本地库", scope_github: "全 GitHub",
    summary_search_github: "GitHub 全站搜「{0}」找到 {1} 个(已并入本地库)",
    github_error: "GitHub 搜索失败:",
    detail_error: "打不开详情:", starred_at: "star 于", last_push: "最后推送",
    delta_recent: "最近一次快照 ▲", unknown_lang: "未知语言",
    because_starred: "因为你 star 过 ", because_liked: "因为你点过感兴趣:",
    hint_tags: "标签 = 仓库作者自己设的 topics(没设的我们自动补);卡片上的标签可以叠加筛选",
  },
  en: {
    tab_trending: "Trending", tab_recommend: "For You", tab_tags: "Tags", tab_starred: "My Stars",
    sort_label: "Sort:",
    sort_trending: "Recent growth", sort_stars: "Total stars",
    sort_pushed: "Recently updated", sort_name: "Name",
    refresh: "↻ Refresh", refresh_batch: "↻ New batch", loading_more: "↻ Loading…",
    batch_hint: "30 per batch; each batch is new",
    loading: "Loading…", no_data: "No data.", error: "Error:",
    open_github: "Open on GitHub ↗", back: "← Back to list",
    interested: "Interested", not_interested: "Not interested",
    chosen_interested: "✓ Interested", chosen_not: "✓ Not interested",
    already: "(already selected)", recording: "Saving…",
    recorded: "(Saved — go back to see changes)", change_hint: "(click the other to change)",
    fail: "Failed: ", author: "by ", intro_label: "Summary:",
    one_line: "Summary", snapshots: "Star snapshots ({0})", readme: "README",
    similar: "Similar repos", similarity: "similarity", no_readme: "No README captured for this repo yet.",
    tags_label: "Tags:",
    tag_remove_hint: "Click to remove this tag",
    tag_add_hint: "Click to add this tag (each one narrows the results)",
    tag_empty: "No repo has all of these tags — click one above to remove it.",
    tagcloud_hint: "Click any tag to browse it; inside, keep clicking tags on cards to narrow down",
    tagcloud_title: "{0} tags covering {1} / {2} repos",
    summary_trending: "Top {2} by star growth ({0} → {1})",
    summary_sorted: "Sorted by {0}, {1} repos",
    summary_tags: "{1} repos tagged “{0}” (by {2})",
    summary_batch: "Batch {0} ({1} repos)",
    batch_more: " · click ↻ for a new batch", batch_end: " · last batch, click ↻ to wrap around",
    summary_starred: "Your {0} starred repos (newest first)",
    summary_search: "{1} results for “{0}”",
    search_empty: "No repos matched.",
    search_placeholder: "Search repos: name / description / tag / README",
    scope_local: "Local", scope_github: "All GitHub",
    summary_search_github: "{1} results from GitHub for “{0}” (merged into your library)",
    github_error: "GitHub search failed: ",
    detail_error: "Cannot open detail: ", starred_at: "starred", last_push: "last push",
    delta_recent: "since last snapshot ▲", unknown_lang: "unknown",
    because_starred: "because you starred ", because_liked: "because you liked ",
    hint_tags: "Tags come from the author's topics (auto-filled when missing); click them on cards to narrow down",
  },
};

let lang = localStorage.getItem("ui_lang") || "zh";

function t(key, ...args) {
  const table = I18N[lang] || I18N.zh;
  let s = table[key] !== undefined ? table[key] : (I18N.zh[key] || key);
  args.forEach((a, i) => { s = s.replace("{" + i + "}", a); });
  return s;
}

const listEl = document.getElementById("list");
const statusEl = document.getElementById("status");
const detailEl = document.getElementById("detail");
const toolbarEl = document.getElementById("toolbar");
const searchEl = document.getElementById("search");
const scopeEl = document.getElementById("scope");

let opinions = {};

const state = {
  tab: "trending",   // trending | recommend | tags | tag | starred | search
  sort: "trending",
  tags: [],          // 当前生效的标签(可多个,之间是「与」)
  offset: 0,         // 推荐视图:第几批
  hasMore: true,
  q: "",             // 搜索关键词
  scope: "local",    // 搜索范围:local = 本地库,github = 全站
  returnTab: "trending",   // 进来点标签之前在哪一页 —— 取消完标签要回到那儿
};
const PAGE = 30;

const SORTS = ["trending", "stars", "pushed", "name"];

function h(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

const LANG_COLORS = {
  Python: "#3572A5", JavaScript: "#f1e05a", TypeScript: "#3178c6",
  Rust: "#dea584", Go: "#00ADD8", Java: "#b07219", C: "#555555",
  "C++": "#f34b7d", Ruby: "#701516", PHP: "#4F5D95", Csharp: "#178600",
  Kotlin: "#A97BFF", Swift: "#F05138", Shell: "#89e051",
};

function languageChip(langName) {
  if (!langName) return h("span", null, t("unknown_lang"));
  const wrap = h("span");
  const dot = h("span", "dot");
  dot.style.background = LANG_COLORS[langName] || "#8b949e";
  wrap.appendChild(dot);
  wrap.appendChild(document.createTextNode(langName));
  return wrap;
}

function nfmt(n) {
  if (n === null || n === undefined) return "?";
  return n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n);
}

function ownerOf(fullName) {
  return (fullName || "").split("/")[0];
}

// 头像:https://github.com/<用户名>.png 是现成入口,会自动跳到头像图。
// 省得再存一份 avatar_url、也省一次 API 调用。
function avatarImg(owner, size) {
  const img = document.createElement("img");
  img.className = "avatar";
  img.src = "https://github.com/" + encodeURIComponent(owner) + ".png?size=" + size;
  img.alt = owner;
  img.loading = "lazy";
  img.referrerPolicy = "no-referrer";
  // 拉不到就清掉 src —— CSS 里给了灰底圆,至少是个占位圈,而不是破图图标
  img.onerror = () => { img.removeAttribute("src"); };
  return img;
}

// 作者(头像 + 名字)。头像就是作者的 icon,所以直接摆在名字前面。
function ownerLink(owner, avatarSize) {
  const wrap = h("span", "owner");
  wrap.appendChild(avatarImg(owner, avatarSize || 32));
  const a = h("a", "owner-link", t("author") + owner);
  a.href = "https://github.com/" + owner;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  wrap.appendChild(a);
  return wrap;
}

// 高亮当前 tab(标签视图没有对应的 tab,就全部取消高亮)
function setActiveTab(tab) {
  document.querySelectorAll(".tab").forEach(b => {
    b.classList.toggle("active", b.dataset.tab === tab);
  });
}

// 点标签 = 叠加/移除。多选之间是「与」:选得越多,结果越窄。
function toggleTag(tag) {
  const wasEmpty = state.tags.length === 0;

  const i = state.tags.indexOf(tag);
  if (i >= 0) state.tags.splice(i, 1);
  else state.tags.push(tag);

  if (wasEmpty) {
    // 第一次点标签:记住当时在哪一页,取消完要回到那儿去
    state.returnTab = state.tab === "tag" ? "trending" : state.tab;
  }

  if (state.tags.length) {
    state.tab = "tag";
    setActiveTab(null);
  } else {
    // 标签清空了 —— 回到点标签之前的那一页,而不是甩到标签云
    state.tab = state.returnTab || "trending";
    setActiveTab(state.tab);
  }
  loadCurrent();
}

// ---- 反馈按钮 ----
function feedbackRow(r, card) {
  const actions = h("div", "actions");
  const ok = h("button", "btn ok");
  const bad = h("button", "btn bad");
  const note = h("span", "vote-note");

  function paint() {
    const cur = opinions[r.full_name];
    ok.classList.toggle("chosen", cur === "interested");
    bad.classList.toggle("chosen", cur === "not_interested");
    ok.textContent = cur === "interested" ? t("chosen_interested") : t("interested");
    bad.textContent = cur === "not_interested" ? t("chosen_not") : t("not_interested");
    if (card.classList.contains("card")) {
      card.style.opacity = cur === "not_interested" ? 0.45 : 1;
    }
    note.textContent = cur ? t("change_hint") : "";
  }

  ok.onclick = () => vote(r.full_name, "interested", paint, note);
  bad.onclick = () => vote(r.full_name, "not_interested", paint, note);
  paint();

  actions.appendChild(ok);
  actions.appendChild(bad);
  actions.appendChild(note);
  return actions;
}

async function vote(fullName, action, paint, note) {
  if (opinions[fullName] === action) {
    note.textContent = t("already");
    return;
  }
  note.textContent = t("recording");
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
    note.textContent = t("recorded");
  } catch (e) {
    note.textContent = t("fail") + e.message;
  }
}

// ---- 卡片 ----
function repoCard(r, opts = {}) {
  const card = h("article", "card");

  const top = h("div", "card-top");
  const owner = ownerOf(r.full_name);
  top.appendChild(avatarImg(owner, 48));
  const nameLink = h("a", "name", r.full_name);
  nameLink.href = "#";
  nameLink.onclick = (e) => { e.preventDefault(); showDetail(r.full_name); };
  top.appendChild(nameLink);

  if (r.because_of) {
    const label = r.because_kind === "interested"
      ? t("because_liked") + r.because_of
      : t("because_starred") + r.because_of;
    top.appendChild(h("span", "reason", label));
  }
  card.appendChild(top);

  // 文本区统一成"一块介绍":
  //   抽到 README 介绍 → 描述行 + 介绍块
  //   没抽到(或跟描述一样) → 只用介绍块装描述
  // 以前是"抽到才显示介绍块",结果有的卡有一块有的没有,看着参差不齐。
  const desc = (r.description || "").trim();
  const intro = (r.intro || "").trim();
  const distinct = intro && intro !== desc;

  if (desc && distinct) card.appendChild(h("p", "desc", desc));

  const boxText = distinct ? intro : desc;
  if (boxText) {
    const box = h("p", "intro");
    box.appendChild(h("span", "intro-label", t("intro_label")));
    box.appendChild(document.createTextNode(" " + boxText));
    card.appendChild(box);
  }

  const meta = h("div", "meta");
  meta.appendChild(ownerLink(owner));
  meta.appendChild(languageChip(r.language));
  meta.appendChild(h("span", null, "★ " + nfmt(r.stargazers_count)));
  if (r.delta !== undefined && r.delta !== null) {
    meta.appendChild(h("span", "delta", "▲ " + r.delta));
  }
  if (r.similarity !== undefined) {
    meta.appendChild(h("span", null, t("similarity") + " " + r.similarity.toFixed(3)));
  }
  if (r.starred_at) {
    meta.appendChild(h("span", null, r.starred_at.slice(0, 10)));
  }
  card.appendChild(meta);

  if (r.topics && r.topics.length) {
    const box = h("div", "topics");
    r.topics.slice(0, 8).forEach(tag => {
      const on = state.tags.includes(tag);
      const chip = h("span", "topic clickable" + (on ? " on" : ""), tag);
      chip.title = on ? t("tag_remove_hint") : t("tag_add_hint");
      chip.onclick = () => toggleTag(tag);
      box.appendChild(chip);
    });
    card.appendChild(box);
  }

  if (opts.feedback) card.appendChild(feedbackRow(r, card));
  return card;
}

// ---- 工具栏 ----
// 右上角那个永远是"重新拉取当前列表";"换一批"是推荐页专属的动作,放在首行工具栏里
function refreshLabel() {
  return t("refresh");
}

async function nextBatch() {
  // 重算一遍没用(同样的输入必然同样的排序),所以要往后翻一段
  state.offset = state.hasMore ? state.offset + PAGE : 0;
  await loadCurrent();
}

function renderToolbar() {
  toolbarEl.replaceChildren();
  toolbarEl.style.display = "flex";
  document.getElementById("refresh").textContent = refreshLabel();

  if (state.tab === "recommend") {
    toolbarEl.appendChild(h("button", "btn batch", t("refresh_batch")))
      .onclick = nextBatch;
    toolbarEl.appendChild(h("span", "muted", t("batch_hint")));
  }

  if (state.tab === "trending" || state.tab === "tag") {
    toolbarEl.appendChild(h("label", null, t("sort_label")));
    const sel = document.createElement("select");
    SORTS.forEach(value => {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = t("sort_" + value);
      if (value === state.sort) opt.selected = true;
      sel.appendChild(opt);
    });
    sel.onchange = () => { state.sort = sel.value; loadCurrent(); };
    toolbarEl.appendChild(sel);
  }

  // 当前生效的标签:只列标签本身,不带 ✕ —— 点标签自己就移除
  if (state.tags.length) {
    toolbarEl.appendChild(h("label", null, t("tags_label")));
    state.tags.forEach(tag => {
      const chip = h("span", "chip", tag);
      chip.title = t("tag_remove_hint");
      chip.onclick = () => toggleTag(tag);
      toolbarEl.appendChild(chip);
    });
  }

  if (state.tab === "tags") {
    toolbarEl.appendChild(h("span", "muted", t("hint_tags")));
  }
}

// ---- 标签云 ----
function renderTagCloud(d) {
  listEl.replaceChildren();
  const card = h("div", "card");
  card.appendChild(h("div", "section-title",
    t("tagcloud_title", d.count, d.tagged_repos, d.total_repos)));
  const cloud = h("div", "tagcloud");
  d.items.forEach(item => {
    const chip = h("span", "topic", `${item.tag} (${item.n})`);
    chip.title = t("tag_add_hint");
    chip.onclick = () => toggleTag(item.tag);
    cloud.appendChild(chip);
  });
  card.appendChild(cloud);
  listEl.appendChild(card);
  statusEl.textContent = t("tagcloud_hint");
}

// ---- 详情 ----
function renderDetail(d) {
  detailEl.replaceChildren();
  listEl.replaceChildren();
  statusEl.textContent = "";
  toolbarEl.style.display = "none";
  detailEl.style.display = "block";

  const back = h("button", "btn back", t("back"));
  back.onclick = () => {
    detailEl.style.display = "none";
    detailEl.replaceChildren();
    loadCurrent();
  };
  detailEl.appendChild(back);

  const head = h("div", "detail-head");
  head.appendChild(avatarImg(ownerOf(d.full_name), 96));
  head.appendChild(h("h2", "detail-title", d.full_name));
  const gh = h("a", "btn gh", t("open_github"));
  gh.href = d.html_url || "#";
  gh.target = "_blank";
  gh.rel = "noopener noreferrer";
  head.appendChild(gh);
  detailEl.appendChild(head);

  if (d.description) detailEl.appendChild(h("p", "detail-desc", d.description));

  const meta = h("div", "detail-meta");
  meta.appendChild(ownerLink(ownerOf(d.full_name)));
  meta.appendChild(languageChip(d.language));
  meta.appendChild(h("span", null, "★ " + nfmt(d.stargazers_count)));
  if (d.delta !== null && d.delta !== undefined) {
    meta.appendChild(h("span", "delta", t("delta_recent") + " " + d.delta));
  }
  if (d.pushed_at) {
    meta.appendChild(h("span", null, t("last_push") + " " + d.pushed_at.slice(0, 10)));
  }
  if (d.starred_at) {
    meta.appendChild(h("span", null, t("starred_at") + " " + d.starred_at.slice(0, 10)));
  }
  detailEl.appendChild(meta);

  if (d.topics && d.topics.length) {
    const box = h("div", "topics");
    d.topics.forEach(tag => {
      const on = state.tags.includes(tag);
      const chip = h("span", "topic clickable" + (on ? " on" : ""), tag);
      chip.title = on ? t("tag_remove_hint") : t("tag_add_hint");
      chip.onclick = () => { detailEl.style.display = "none"; toggleTag(tag); };
      box.appendChild(chip);
    });
    detailEl.appendChild(box);
  }

  detailEl.appendChild(feedbackRow(d, detailEl));

  const introText = (d.intro || "").trim();
  if (introText && introText !== (d.description || "").trim()) {
    const box = h("div", "detail-intro");
    box.appendChild(h("div", "section-title", t("one_line")));
    box.appendChild(h("p", null, introText));
    detailEl.appendChild(box);
  }

  if (d.history && d.history.length) {
    const box = h("div", "detail-intro");
    box.appendChild(h("div", "section-title", t("snapshots", d.history.length)));
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
    box.appendChild(chart);
    detailEl.appendChild(box);
  }

  const rbox = h("div", "detail-intro");
  rbox.appendChild(h("div", "section-title", t("readme")));
  if (d.readme && d.readme.trim()) {
    const pre = h("pre", "readme");
    pre.textContent = d.readme;
    rbox.appendChild(pre);
  } else {
    rbox.appendChild(h("p", "muted", t("no_readme")));
  }
  detailEl.appendChild(rbox);

  if (d.similar && d.similar.length) {
    const box = h("div", "detail-intro");
    box.appendChild(h("div", "section-title", t("similar")));
    d.similar.forEach(s => {
      const row = h("div", "similar-row");
      const a = h("a", "name", s.full_name);
      a.href = "#";
      a.onclick = (e) => { e.preventDefault(); showDetail(s.full_name); };
      row.appendChild(a);
      row.appendChild(h("span", "muted",
        `  ${s.language || "?"} · ★${nfmt(s.stargazers_count)} · ${t("similarity")} ${s.similarity.toFixed(3)}`));
      box.appendChild(row);
    });
    detailEl.appendChild(box);
  }
}

async function showDetail(fullName) {
  detailEl.style.display = "block";
  detailEl.replaceChildren();
  listEl.replaceChildren();
  statusEl.textContent = t("loading");
  toolbarEl.style.display = "none";

  try {
    const op = await getJSON("/api/opinions");
    opinions = op.opinions || {};
    const d = await getJSON("/api/repos/" + fullName);
    renderDetail(d);
  } catch (e) {
    detailEl.replaceChildren();
    statusEl.textContent = t("detail_error") + e.message;
  }
}

// ---- 列表 ----
function render(items, opts) {
  listEl.replaceChildren();
  if (!items.length) {
    statusEl.textContent = opts.empty || t("no_data");
    return;
  }
  items.forEach(r => listEl.appendChild(repoCard(r, opts)));
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
  return copy;
}

async function loadCurrent() {
  detailEl.style.display = "none";
  detailEl.replaceChildren();
  listEl.replaceChildren();
  toolbarEl.style.display = "flex";
  renderToolbar();
  statusEl.textContent = t("loading");

  try {
    const op = await getJSON("/api/opinions");
    opinions = op.opinions || {};

    if (state.tab === "trending" || state.tab === "tag") {
      const p = new URLSearchParams({ sort: state.sort, limit: 30 });
      state.tags.forEach(x => p.append("tag", x));   // 多标签:重复参数
      const d = await getJSON("/api/repos?" + p.toString());
      let summary;
      if (state.tags.length) {
        summary = t("summary_tags", state.tags.join(" + "), d.count,
                    t("sort_" + state.sort));
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
        summary: t("summary_batch", batch, d.items.length),
      });
    } else if (state.tab === "tags") {
      renderTagCloud(await getJSON("/api/tags?limit=200"));
    } else if (state.tab === "search") {
      const p = new URLSearchParams({ q: state.q, limit: 60, scope: state.scope });
      const d = await getJSON("/api/search?" + p.toString());
      render(d.items, {
        feedback: true,
        summary: d.scope === "github"
          ? t("summary_search_github", d.q, d.count)
          : t("summary_search", d.q, d.count),
        empty: t("search_empty"),
      });
    } else {
      const d = await getJSON("/api/me/starred?limit=200");
      render(d.items, { feedback: false, summary: t("summary_starred", d.count) });
    }
  } catch (e) {
    statusEl.textContent = t("error") + e.message;
  }
}

function applyI18n() {
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  searchEl.placeholder = t("search_placeholder");
  scopeEl.options[0].textContent = t("scope_local");
  scopeEl.options[1].textContent = t("scope_github");
  document.getElementById("lang").textContent = lang === "zh" ? "EN" : "中";
}

document.querySelectorAll(".tab").forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.tab = btn.dataset.tab;
    state.tags = [];
    if (state.tab === "recommend") {
      state.sort = "trending";
      state.offset = 0;
    }
    loadCurrent();
  };
});

// 搜索:回车就搜。范围可选"本地库"或"全 GitHub"。
searchEl.addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  const q = searchEl.value.trim();
  if (!q) return;
  state.q = q;
  state.scope = scopeEl.value || "local";
  state.tab = "search";
  setActiveTab(null);
  loadCurrent();
});

// 换了搜索范围就把当前搜索重跑一遍,不用再按一次回车
scopeEl.onchange = () => {
  state.scope = scopeEl.value;
  if (state.tab === "search" && state.q) loadCurrent();
};

document.getElementById("lang").onclick = () => {
  lang = lang === "zh" ? "en" : "zh";
  localStorage.setItem("ui_lang", lang);
  applyI18n();
  loadCurrent();
};

// 刷新:在推荐页是"换一批"(重算没用 —— 同样的输入必然同样的排序)。
document.getElementById("refresh").onclick = () => {
  const btn = document.getElementById("refresh");
  if (state.tab === "recommend") {
    state.offset = state.hasMore ? state.offset + PAGE : 0;
  }
  btn.textContent = t("loading_more");
  loadCurrent().finally(() => { btn.textContent = refreshLabel(); });
};

applyI18n();
loadCurrent();
