#!/usr/bin/env python3
"""README 文本处理:抽"介绍"(列表卡片用)和转"可读正文"(详情页用)。

背景(踩过的坑):
    第一版存 README 时把换行压成了空格,导致只能在一整行里瞎猜正文在哪 ——
    public-apis 那种开头 20 行全是广告的 README,怎么猜都会猜中广告。
    现在存库保留了换行,于是可以按结构判断:标题、列表、引用、代码块直接跳过,
    真正的正文段落自然浮出来。换行是免费的结构信息,当初压掉它是个错误。

两道保险:
    1. 段落级过滤:跳过 markdown 结构、语言选择器、广告横幅
    2. 和 description 比对:选中的段落若和描述毫无重合,说明大概率选错了,宁可退回 description
"""
import html
import re

BADGE_RE = re.compile(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)")   # [![Build](img)](link)
IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")                  # ![alt](img)
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")                # [文字](链接) → 文字
HTML_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
BULLET_RE = re.compile(r"^([-*+•]\s|\d+[.)]\s)")              # 列表项
CJK_RE = re.compile(r"[一-鿿]")

NOISE_HINTS = (
    "table of contents", "installation", "quick start", "getting started",
    "documentation", "contributing", "changelog", "acknowledg", "license",
    "目录", "安装", "快速开始", "贡献", "许可证", "更新日志",
    "sponsor", "powered by", "promo", "discount", "coupon", "buy now",
    "backed by", "supported by", "sign up", "free trial", "unified suite",
    "read this in other languages", "this page is available",
)

LANGUAGE_NAMES = (
    "english", "简体中文", "繁體中文", "日本語", "한국어", "deutsch", "español",
    "français", "русский", "português", "italiano", "العربية", "türkçe",
    "polski", "ไทย", "tiếng việt", "עברית", "ελληνικά", "فارسی",
)

MIN_OVERLAP = 0.25     # 和 description 的词重合度低于此值,就不敢用 README 里的话
MAX_PARAGRAPHS = 12

# 项目名后面紧跟这些词时,它是句子的主语,不是标题 —— 这时不能把名字切掉。
# 例如 "yt-dlp is a feature-rich..." 切掉会变成 "is a feature-rich...",读起来莫名其妙。
VERB_AFTER_NAME = (
    "is", "are", "was", "were", "provides", "allows", "lets", "helps",
    "makes", "can", "will", "has", "have", "offers", "enables", "aims",
    "serves", "supports", "brings", "gives", "是一个", "是", "提供",
)


def _strip_markdown(text):
    """剥掉行内 markdown 结构,只留文字(不动换行 —— 换行在切段落时就要用掉)。"""
    t = html.unescape(text)
    t = BADGE_RE.sub(" ", t)
    t = IMG_RE.sub(" ", t)
    t = LINK_RE.sub(r"\1", t)
    t = HTML_RE.sub(" ", t)
    t = re.sub(r"={3,}", " ", t)
    t = re.sub(r"[*#>`]+", " ", t)      # 强调/标题/引用符号
    t = WS_RE.sub(" ", t)
    return t.strip(" -—·\t")


def _paragraphs(readme):
    """把 README 切成候选段落。

    跳过:代码块(``` 围起来的)、标题(#)、列表项、引用(>)、表格行。
    把连续的普通文本行并成一段 —— README 里的段落经常是硬换行的,
    不并起来会得到一堆半截句子。
    """
    buf = []
    in_code = False
    for raw in readme.split("\n"):
        line = raw.strip()

        if line.startswith("```") or line.startswith("~~~"):
            in_code = not in_code
            if buf:
                yield " ".join(buf)
                buf = []
            continue
        if in_code:
            continue

        if not line:                                   # 空行 = 段落结束
            if buf:
                yield " ".join(buf)
                buf = []
            continue

        if line[0] in "#>|" or BULLET_RE.match(line):  # 结构行,不是正文
            if buf:
                yield " ".join(buf)
                buf = []
            continue

        buf.append(line)

    if buf:
        yield " ".join(buf)


def _is_noise(s):
    """这一段像不像"正经介绍"?不像就返回 True。"""
    if len(s) < 30:
        return True
    low = s.lower()
    if any(h in low for h in NOISE_HINTS):
        return True
    if sum(1 for name in LANGUAGE_NAMES if name in low) >= 4:
        return True
    if "](http" in low or "http://" in s or "https://" in s:
        return True
    if sum(c.isalnum() for c in s) < len(s) * 0.5:
        return True
    if "=>" in s or "::" in s:
        return True
    return False


def _words(s):
    """句子里的"实词"集合:英文取长度>3 的词,中文取两字以上的连续汉字。"""
    words = set(re.findall(r"[a-z0-9]{4,}", (s or "").lower()))
    words |= {w for w in re.findall(r"[一-鿿]{2,}", s or "")}
    return words


def _overlap(sentence, target_words):
    if not target_words:
        return 0.0
    return len(_words(sentence) & target_words) / len(target_words)


def _trim(s, max_len):
    if len(s) <= max_len:
        return s
    cut = s[:max_len]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip() + "…"


def extract_intro(readme, description="", repo_name="", max_len=220):
    """返回一段介绍;找不到可靠的正文就退回 description。"""
    if readme:
        name = (repo_name or "").split("/")[-1].lower()
        candidates = []
        for para in list(_paragraphs(readme))[:MAX_PARAGRAPHS]:
            s = _strip_markdown(para)
            # 段落开头常常粘着项目名(原 README 的标题行),去掉。
            # 但如果名字后面是个动词,说明它是句子主语,切掉会把句子弄残。
            if name and s.lower().startswith(name):
                rest = s[len(name):]
                if rest[:1] in (" ", "", ":", "-", "—", "·"):
                    tail = rest.strip().lower()
                    if not tail.startswith(VERB_AFTER_NAME):
                        s = rest.lstrip(" :‑-—·")
            if not _is_noise(s):
                candidates.append(s)

        if candidates:
            target = _words(description)
            best = max(candidates, key=lambda s: _overlap(s, target))
            if _overlap(best, target) >= MIN_OVERLAP:
                return _trim(best, max_len)
            # 拿不准就退回 description:短,但一定不会把广告当介绍
            if description:
                return description.strip()
            return _trim(candidates[0], max_len)

    return (description or "").strip()


def readable(readme, max_chars=2600):
    """详情页用:把 README 清理成可读的纯文本,保留换行和段落。"""
    if not readme:
        return ""

    text = html.unescape(readme)
    text = BADGE_RE.sub(" ", text)
    text = IMG_RE.sub(" ", text)
    text = LINK_RE.sub(r"\1", text)          # 链接只留文字
    text = HTML_RE.sub(" ", text)

    out = []
    in_code = False
    for raw in text.split("\n"):
        line = raw.rstrip()
        if line.strip().startswith("```") or line.strip().startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue
        line = WS_RE.sub(" ", line).strip()
        line = re.sub(r"^#{1,6}\s*", "", line)          # 标题符号去掉,文字留下
        line = re.sub(r"^[-*+•]\s+", "· ", line)        # 列表统一成 ·
        line = line.replace("**", "").replace("__", "")
        out.append(line)

    # 连续空行压成一个
    merged = []
    for line in out:
        if not line and merged and not merged[-1]:
            continue
        merged.append(line)

    return "\n".join(merged).strip()[:max_chars]
