// P8:前端逻辑。原生 JS,没有框架 —— 目标是把 fetch + DOM 用熟,不是学框架。
//
// 两个视图:
//   列表视图  三个 tab(Trending / 推荐 / 我的)
//   详情视图  点任意 repo 名字进入,展示 README 正文等
const API = "http://127.0.0.1:8000";

const listEl = document.getElementById("list");
const statusEl = document.getElementById("status");
const detailEl = document.getElementById("detail");

// 当前态度 {full_name: "interested" | "not_interested"}
let opinions = {};
// 记住从哪个 tab 进来的,详情页返回时回到原处
let currentTab = "trending";

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

function languageChip(lang) {
  if (!lang) return h("span", null, "未知语言");
  const wrap = h("span");
  const dot = h("span", "dot");
  dot.style.background = LANG_COLORS[lang] || "#8b949e";
  wrap.appendChild(dot);
  wrap.appendChild(document.createTextNode(lang));
  return wrap;
}

function nfmt(n) {
  if (n === null || n === undefined) return "?";
  return n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n);
}

// ---- 反馈按钮:可以随时改主意 ----
function feedbackRow(r, card) {
  const actions = h("div", "actions");
  const ok = h("button", "btn ok");
  const bad = h("button", "btn bad");
  const note = h("span", "vote-note");

  function paint() {
    const cur = opinions[r.full_name];
    ok.classList.toggle("chosen", cur === "interested");
    bad.classList.toggle("chosen", cur === "not_interested");
    ok.textContent = cur === "interested" ? "✓ 已选:感兴趣" : "感兴趣";
    bad.textContent = cur === "not_interested" ? "✓ 已选:不感兴趣" : "不感兴趣";
    if (card.classList.contains("card")) {
      card.style.opacity = cur === "not_interested" ? 0.45 : 1;
    }
    note.textContent = cur ? "(再点另一个可以改)" : "";
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
    note.textContent = "(已经是这个了)";
    return;
  }
  note.textContent = "记录中…";
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
    note.textContent = "(已记录,回列表看推荐变化)";
  } catch (e) {
    note.textContent = "失败:" + e.message;
  }
}

// ---- 列表卡片 ----
function repoCard(r, opts = {}) {
  const card = h("article", "card");

  const top = h("div", "card-top");
  // 名字改成"进详情页",不再直接跳到 GitHub。
  // 想跳 GitHub 的话,详情页里给了明确的按钮 —— 列表里误点跳走太烦。
  const nameLink = h("a", "name", r.full_name);
  nameLink.href = "#";
  nameLink.onclick = (e) => { e.preventDefault(); showDetail(r.full_name); };
  top.appendChild(nameLink);

  if (r.because_of) {
    const label = r.because_kind === "interested"
      ? "因为你点过感兴趣:" + r.because_of
      : "因为你 star 过 " + r.because_of;
    top.appendChild(h("span", "reason", label));
  }
  card.appendChild(top);

  if (r.description) card.appendChild(h("p", "desc", r.description));

  if (r.intro && r.intro.trim() && r.intro.trim() !== (r.description || "").trim()) {
    const box = h("p", "intro");
    box.appendChild(h("span", "intro-label", "介绍:"));
    box.appendChild(document.createTextNode(" " + r.intro));
    card.appendChild(box);
  }

  const meta = h("div", "meta");
  meta.appendChild(languageChip(r.language));
  meta.appendChild(h("span", null, "★ " + nfmt(r.stargazers_count)));
  if (r.delta !== undefined && r.delta !== null) {
    meta.appendChild(h("span", "delta", "▲ " + r.delta + " (自 " + opts.since + ")"));
  }
  if (r.similarity !== undefined) {
    meta.appendChild(h("span", null, "相似度 " + r.similarity.toFixed(3)));
  }
  if (r.starred_at) {
    meta.appendChild(h("span", null, "star 于 " + r.starred_at.slice(0, 10)));
  }
  card.appendChild(meta);

  if (r.topics && r.topics.length) {
    const box = h("div", "topics");
    r.topics.slice(0, 8).forEach(t => box.appendChild(h("span", "topic", t)));
    card.appendChild(box);
  }

  if (opts.feedback) card.appendChild(feedbackRow(r, card));
  return card;
}

// ---- 详情视图 ----
// 这是这次新增的重点:点进来看 README 正文,而不是跳到 GitHub。
function renderDetail(d) {
  detailEl.replaceChildren();
  listEl.replaceChildren();
  statusEl.textContent = "";
  detailEl.style.display = "block";

  // 返回
  const back = h("button", "btn back", "← 返回列表");
  back.onclick = () => {
    detailEl.style.display = "none";
    detailEl.replaceChildren();
    loadTab(currentTab);
  };
  detailEl.appendChild(back);

  const head = h("div", "detail-head");
  head.appendChild(h("h2", "detail-title", d.full_name));

  const gh = h("a", "btn gh", "在 GitHub 打开 ↗");
  gh.href = d.html_url || "#";
  gh.target = "_blank";
  gh.rel = "noopener noreferrer";
  head.appendChild(gh);
  detailEl.appendChild(head);

  if (d.description) detailEl.appendChild(h("p", "detail-desc", d.description));

  // 关键数字
  const meta = h("div", "detail-meta");
  meta.appendChild(languageChip(d.language));
  meta.appendChild(h("span", null, "★ " + nfmt(d.stargazers_count)));
  if (d.delta !== null && d.delta !== undefined) {
    meta.appendChild(h("span", "delta", "最近一次快照 ▲ " + d.delta));
  }
  if (d.pushed_at) meta.appendChild(h("span", null, "最后推送 " + d.pushed_at.slice(0, 10)));
  if (d.starred_at) meta.appendChild(h("span", null, "你 star 于 " + d.starred_at.slice(0, 10)));
  detailEl.appendChild(meta);

  if (d.topics && d.topics.length) {
    const box = h("div", "topics");
    d.topics.forEach(t => box.appendChild(h("span", "topic", t)));
    detailEl.appendChild(box);
  }

  // 反馈(详情页里也能表态)
  detailEl.appendChild(feedbackRow(d, detailEl));

  // 介绍
  const introText = (d.intro || "").trim();
  if (introText && introText !== (d.description || "").trim()) {
    const box = h("div", "detail-intro");
    box.appendChild(h("div", "section-title", "一句话介绍"));
    box.appendChild(h("p", null, introText));
    detailEl.appendChild(box);
  }

  // star 快照历史 —— 用几根柱子画,不用图表库
  if (d.history && d.history.length) {
    const box = h("div", "detail-intro");
    box.appendChild(h("div", "section-title", `star 快照(${d.history.length} 次)`));
    const chart = h("div", "chart");
    const vals = d.history.map(x => x.stargazers_count);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    d.history.forEach(x => {
      const col = h("div", "chart-col");
      const bar = h("div", "chart-bar");
      // 高度按区间归一化;全相等时给个中间高度,免得除零
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

  // README 正文 —— 详情页存在的意义:不靠猜,直接把原文给你看
  const box = h("div", "detail-intro");
  box.appendChild(h("div", "section-title", "README 正文"));
  if (d.readme && d.readme.trim()) {
    const pre = h("pre", "readme");
    pre.textContent = d.readme;          // textContent,不是 innerHTML
    box.appendChild(pre);
  } else {
    box.appendChild(h("p", "muted", "库里还没抓到这个 repo 的 README。"));
  }
  detailEl.appendChild(box);

  // 相似的 repo
  if (d.similar && d.similar.length) {
    const box = h("div", "detail-intro");
    box.appendChild(h("div", "section-title", "相似的 repo"));
    d.similar.forEach(s => {
      const row = h("div", "similar-row");
      const a = h("a", "name", s.full_name);
      a.href = "#";
      a.onclick = (e) => { e.preventDefault(); showDetail(s.full_name); };
      row.appendChild(a);
      row.appendChild(h("span", "muted",
        `  ${s.language || "?"} · ★${nfmt(s.stargazers_count)} · 相似度 ${s.similarity.toFixed(3)}`));
      box.appendChild(row);
    });
    detailEl.appendChild(box);
  }
}

async function showDetail(fullName) {
  detailEl.style.display = "block";
  detailEl.replaceChildren();
  listEl.replaceChildren();
  statusEl.textContent = "加载中…";

  try {
    const op = await getJSON("/api/opinions");
    opinions = op.opinions || {};
    const d = await getJSON("/api/repos/" + fullName);
    renderDetail(d);
  } catch (e) {
    detailEl.replaceChildren();
    statusEl.textContent = "打不开详情:" + e.message;
  }
}

// ---- 列表 ----
function render(items, opts) {
  listEl.replaceChildren();
  if (!items.length) {
    statusEl.textContent = "没有数据。";
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

async function loadTab(tab) {
  currentTab = tab;
  detailEl.style.display = "none";
  detailEl.replaceChildren();
  listEl.replaceChildren();
  statusEl.textContent = "加载中…";

  try {
    const op = await getJSON("/api/opinions");
    opinions = op.opinions || {};

    if (tab === "trending") {
      const d = await getJSON("/api/repos?sort=trending&limit=30");
      render(d.items, {
        feedback: true, since: d.since,
        summary: `近两个快照日(${d.since} → ${d.as_of})star 增量 Top ${d.items.length}`,
      });
    } else if (tab === "recommend") {
      const d = await getJSON("/api/recommend?limit=30");
      render(d.items, {
        feedback: true,
        summary: `根据你 star 过 + 点过感兴趣的口味推的 ${d.items.length} 个`,
      });
    } else {
      const d = await getJSON("/api/me/starred?limit=200");
      render(d.items, {
        feedback: false,
        summary: `你 star 过的 ${d.count} 个 repo(按 star 时间倒序)`,
      });
    }
  } catch (e) {
    statusEl.textContent = "出错了:" + e.message;
  }
}

document.querySelectorAll(".tab").forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    loadTab(btn.dataset.tab);
  };
});

loadTab("trending");
