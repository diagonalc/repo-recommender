#!/usr/bin/env python3
"""前端自检:语法 + 文案表一致性 + 死代码。

为什么需要它(三件事都是真出过的):
  1. **语法**:这台机器没有 node,前端改完没法 `node --check`。
     JS 写错一个括号,页面上就是白屏 —— 而且不报在服务器日志里,只能开
     浏览器控制台才看得到。这个脚本用真的 JS 解析器(esprima)把这一关补上。
  2. **文案表对齐**:文案都走 t("key")。漏定义一个 key,页面上会**直接把
     some_key 当文字显示出来**,而且只在切到某个语言时才出现。
  3. **死代码**:换一批 / 上一批 删掉之后,对应的文案 key 和图标还留着。
     留着不算 bug,但下次改的人会以为它们还有用。

跑法:
    .venv/bin/python tests/check_frontend.py

依赖 esprima(纯 Python 的 JS 解析器,不用装 node):
    .venv/bin/python -m pip install esprima
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import esprima
    from esprima.nodes import Node
except ImportError:
    print("需要 esprima:.venv/bin/python -m pip install esprima")
    sys.exit(2)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(BASE, "web", "app.js")

FAILED = []
WARNED = []


def check(name, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def warn(name, detail=""):
    print(f"  ⚠️  {name}" + (f"  {detail}" if detail else ""))
    WARNED.append(name)


def walk(node, fn):
    """深度遍历 AST。

    ⚠️ esprima-python 返回的是 nodes.Node **对象**,不是 dict ——
    用 isinstance(x, dict) 判断会一个节点都走不到(踩过)。
    节点的字段挂在实例属性上,所以用 vars()。
    """
    if isinstance(node, Node):
        fn(node)
        for value in vars(node).values():
            walk(value, fn)
    elif isinstance(node, (list, tuple)):
        for value in node:
            walk(value, fn)


def subtree(node):
    """收集一棵子树里的所有节点(含自身)。"""
    out = []
    walk(node, out.append)
    return out


def all_string_literals(tree):
    """整个文件里出现过的所有字符串字面量。

    为什么需要它:图标和文案大量是通过**字符串参数**传的 ——
        iconSpan("comment", 21)
        t(lang === "zh" ? "lang_zh" : "lang_en")
    只认 ICONS.comment / t("literal") 这种写法,就会把这些全判成"没人用",
    报出一堆假的死代码。宁可用"这个名字在文件里出现过吗"这种宽口径 ——
    它的误判方向是**漏报死代码**,而不是虚报,后者会让人不再信任这个脚本。
    """
    out = set()

    def grab(n):
        if n.type == "Literal" and isinstance(getattr(n, "value", None), str):
            out.add(n.value)
    walk(tree, grab)
    return out


# 这些函数的**第一个参数是文案 key**,不是已经翻好的文字。
# 少列一个,它用到的 key 就会被误判成"没人用"(死代码),反之则漏报。
KEY_FUNCS = {"t", "setTitle"}


def prop_key(p):
    """取对象字面量某个属性的键名(支持 {a:1} / {"a":1} / {a} 三种写法)。

    ⚠️ Identifier 和 Literal 取值方式不同:前者是 .name,后者才是 .value。
    写成统一的 .value 会全都拿到 None —— 表现是"表就在那儿,但一个 key 都读不出来"。
    """
    k = getattr(p, "key", None)
    if k is None:
        return None
    t = getattr(k, "type", None)
    if t == "Identifier":
        return getattr(k, "name", None)
    if t == "Literal":
        return getattr(k, "value", None)
    return None


def object_keys(node):
    """取一个 ObjectExpression 的所有键名。"""
    return {k for k in (prop_key(p) for p in getattr(node, "properties", [])) if k}


def main():
    src = open(APP_JS, encoding="utf-8").read()

    # ---------- 1. 语法 ----------
    print("1. 语法(真正的 JS 解析)")
    # esprima-python 停在 ES2017,不认识 ES2019 的"无参 catch"(`catch {`)。
    # 这是**解析器的局限,不是代码问题** —— 补一个形参再喂给它。
    # 只改内存里这份字符串,不动磁盘上的文件;行号也不变。
    parse_src = re.sub(r"\bcatch\s*\{", "catch (_e) {", src)
    try:
        tree = esprima.parseScript(parse_src, {"loc": True, "tolerant": False})
        check("web/app.js 能被解析", True, f"({len(src.splitlines())} 行)")
    except Exception as e:
        check("web/app.js 能被解析", False, f"{getattr(e, 'lineNumber', '?')} 行:{e}")
        print("\n语法都不对,后面不用查了。")
        sys.exit(1)

    # ---------- 2. 文案表 zh/en 对齐 ----------
    print("\n2. 文案表 I18N 的 zh / en 对齐")
    i18n = {}

    def grab_i18n(n):
        if n.type != "VariableDeclarator":
            return
        if getattr(getattr(n, "id", None), "name", None) != "I18N":
            return
        for lang_prop in getattr(n.init, "properties", []):
            i18n[prop_key(lang_prop)] = object_keys(lang_prop.value)
    walk(tree, grab_i18n)

    zh, en = i18n.get("zh", set()), i18n.get("en", set())
    check("抓到 zh / en 两张表", bool(zh and en), f"(zh {len(zh)} 条 / en {len(en)} 条)")
    only_zh, only_en = sorted(zh - en), sorted(en - zh)
    check("没有只在 zh 里的 key", not only_zh, ", ".join(only_zh[:8]))
    check("没有只在 en 里的 key", not only_en, ", ".join(only_en[:8]))

    # ---------- 3. 用到的 key 都有定义 ----------
    print("\n3. 代码里 t(...) 用到的 key 是否都有定义")
    used, dynamic = set(), set()

    def collect_keys(node):
        """只沿着**会产生 key 的位置**往下走。

        不能无脑扫整棵子树:t(state.scope === "github" ? "summary_search_github"
        : "summary_search") 里的 "github" 是**比较用的操作数**,不是 key。
        无脑扫会把它当成"用到了叫 github 的文案",于是天天报假失败。

        认的位置:字符串字面量 / 加号拼接(取固定前缀)/ 三元(走两个分支)。
        """
        t = getattr(node, "type", None)
        if t == "Literal" and isinstance(getattr(node, "value", None), str):
            used.add(node.value)
        elif t == "BinaryExpression" and getattr(node, "operator", None) == "+":
            # 拼接的每一段:是字面量就只当**前缀**记下来,别再塞进 used。
            # 塞进去的话 "tab_" 本身会被当成一个"用到的 key",
            # 然后 I18N 里找不到它 → 天天报一条假失败。
            for side in (getattr(node, "left", None), getattr(node, "right", None)):
                if getattr(side, "type", None) == "Literal":
                    dynamic.add(side.value)   # t("tab_" + state.tab) → 记下 "tab_"
                else:
                    collect_keys(side)
        elif t == "ConditionalExpression":
            collect_keys(node.consequent)
            collect_keys(node.alternate)
        # 其它(变量、比较式、函数调用…)静态看不出来,忽略

    def grab_t(n):
        if n.type != "CallExpression":
            return
        if getattr(getattr(n, "callee", None), "name", None) not in KEY_FUNCS:
            return
        args = getattr(n, "arguments", [])
        if args:                     # 只有第一个参数是 key,后面的是插值
            collect_keys(args[0])
    walk(tree, grab_t)

    missing = sorted(k for k in used if k not in zh)
    check("用到的 key 都定义了", not missing, ", ".join(missing[:10]))
    if dynamic:
        warn(f"有 {len(dynamic)} 个 key 是运行时拼的,静态查不了",
             " ".join(f"{p}*" for p in sorted(dynamic)))

    # index.html 也要一起看 —— key 目前只在 app.js 里用,
    # 但"假设它一定不会出现在 HTML 里"是没必要的风险,读一下很便宜。
    html_src = open(os.path.join(BASE, "web", "index.html"), encoding="utf-8").read()

    # 动态前缀覆盖到的 key(比如 tab_ + state.tab)不算死代码
    covered = set()
    for prefix in dynamic:
        covered |= {k for k in zh if k.startswith(prefix)}
    unused = sorted(k for k in (zh - used - covered) if k not in html_src)
    if unused:
        warn(f"{len(unused)} 个文案 key 定义了但没人用", ", ".join(unused[:12]))
    else:
        print("  ✅ 没有无人引用的文案 key")

    # ---------- 4. 图标表 ----------
    print("\n4. 图标表 ICONS")
    icons = set()

    def grab_icons(n):
        if n.type != "VariableDeclarator":
            return
        if getattr(getattr(n, "id", None), "name", None) != "ICONS":
            return
        icons.update(object_keys(n.init))
    walk(tree, grab_icons)

    # 两种用法都要认:ICONS.xxx,以及 iconSpan("xxx") 这种字符串传参。
    strings = all_string_literals(tree)
    used_icons = {i for i in icons if i in strings} | \
                 set(re.findall(r"ICONS\.([A-Za-z0-9_]+)", src))
    check("抓到 ICONS", bool(icons), f"({len(icons)} 个)")
    bad = sorted(used_icons - icons)
    check("用到的图标都存在", not bad, ", ".join(bad))
    dead_icons = sorted(icons - used_icons)
    if dead_icons:
        warn(f"{len(dead_icons)} 个图标定义了但没人用", ", ".join(dead_icons))
    else:
        print("  ✅ 没有无人引用的图标")

    # ---------- 5. HTML 引用的资源 ----------
    print("\n5. index.html 引用的文件存在吗")
    html = open(os.path.join(BASE, "web", "index.html"), encoding="utf-8").read()
    for m in re.findall(r'<script[^>]+src="([^"]+)"', html):
        path = m.split("?")[0]
        check(f"脚本 {m} 存在", os.path.exists(os.path.join(BASE, "web", path)))

    # ---------- 6. 网页字体的子集完整性 ----------
    # 兔子洞标题用的是**子集化的**日文字体(全量 4.18 MB,裁到 2 KB)。
    # 这里防的是:**子集生成失败时,文件同样是"很小"的** ——
    # 只检查大小会以为成功。真出过这么一次:
    # 生成命令里用了 shell 变量、展开失败变成空字符串,
    # 于是产出的是一个 500 字节的**空字体**(只有 1 个 .notdef 字形、连 cmap 都没有),
    # 而当时我只看了大小就当成"缩小了 8771 倍"发出去了 —— 页面上自然毫无变化。
    #
    # 所以这里查的是**内容**:取 cmap(字符→字形 的映射表),
    # 空子集的映射数是 0,正常子集至少有好几个。
    print("\n6. 网页字体(子集里必须真的有字形)")
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        warn("没装 fonttools,跳过字体检查", "(pip install fonttools)")
    else:
        # 注意允许后面跟 ?v=xxxx —— 字体 URL 现在带内容哈希做缓存失效,
        # 写成"必须以 .woff2 结尾"会一个都匹配不到(那样测试会静默失效)
        # 兔子洞标题 —— 字体就是照它子集化的,所以必须能覆盖它每一个字。
        # 从 app.js 里读出来,而不是在这儿再抄一遍:抄一遍就迟早会抄漏。
        m = re.search(r'ACG_TITLE\s*=\s*"([^"]+)"', src)
        title = m.group(1) if m else ""
        if not title:
            warn("没找到 ACG_TITLE,没法核对字体覆盖")
        refs = re.findall(r'url\("(/[^"?]+\.woff2?)(?:\?[^"]*)?"\)', html)
        if not refs:
            print("  (样式里没有引用字体文件)")
        for ref in refs:
            path = os.path.join(BASE, "web", os.path.basename(ref))
            if not os.path.exists(path):
                check(f"{ref} 存在", False)
                continue
            cmap = TTFont(path).getBestCmap() or {}
            check(f"{ref} 里有字形映射", len(cmap) >= 2, f"({len(cmap)} 个字符)")
            if title:
                # 这条是真会咬人的:改了标题却没重新生成子集,
                # 少的那几个字会静默地掉回系统字体 —— 页面上只有它们长得不一样
                missing = sorted({c for c in title if ord(c) not in cmap})
                check(f"{ref} 覆盖标题「{title}」", not missing,
                      f"缺 {''.join(missing)} —— 要重新生成子集" if missing else "")

    print()
    if FAILED:
        print(f"❌ {len(FAILED)} 项失败:")
        for f in FAILED:
            print(f"     {f}")
    else:
        print("✅ 硬性问题:全部通过")
    if WARNED:
        print(f"⚠️  {len(WARNED)} 项提醒(不影响运行,建议清理)")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
