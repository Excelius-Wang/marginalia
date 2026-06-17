#!/usr/bin/env python3
"""Publish a marginalia markdown note to a Feishu/Lark document.

Pipeline (see references/feishu-publish.md):
  1. parse the md note (front matter-less; `# title`, `## sections`, bullets)
  2. convert md -> lark-doc DocxXML (headings/lists/bold/code/inline $latex$)
  3. extract key figures from the source PDF (extract_figures.py) using the
     `Fig.N [p.P]` tags in the note's "Key Artifacts" section
  4. create the doc via `lark-cli docs +create`; append a "图表 Figures" section
  5. media-insert each figure (append-to-end, in order, with caption)
  6. (later phases) place under Wiki domain node; upsert Base index row
  7. record the doc URL back into the note + .marginalia/feishu.json mapping

This module shells out to `lark-cli` (user identity). Run `lark-cli auth status`
first; it must show a user identity. Deterministic + idempotent via the mapping.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import extract_figures as ef

# ---------------------------------------------------------------- md -> DocxXML

INLINE_CODE = re.compile(r"`([^`]+)`")
DISPLAY_LATEX = re.compile(r"\$\$(.+?)\$\$", re.S)
INLINE_LATEX = re.compile(r"\$([^$]+)\$")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
# Semantic inline color the agent authors in the note: {{c:term}} -> colored span.
# Different colors carry different meaning (see references/style-guide.md):
#   b 蓝=专名(模型/方法/系统/数据集/benchmark)  p 紫=机制/技术概念
#   o 橙=关键指标/数字结论  g 绿=正面判断/优势  r 红=风险/短板/批判
COLOR = re.compile(r"\{\{([bpogr]):(.+?)\}\}", re.S)
CMAP = {"b": "blue", "p": "purple", "o": "orange", "g": "green", "r": "red"}
# Figure control tags ([p.N]/[hero]/[@anchor]) are parsing directives, not content;
# parse_figures reads them off the raw md, so strip them from the rendered text.
CONTROL_TAGS = re.compile(r"\s*\[(?:p\.\d+|hero|@[^\]]*|box=[^\]]*)\]")
ORDERED = re.compile(r"^(\s*)\d+\.\s+")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")

# Semantic routing: marginalia's fixed section titles -> a colored callout.
# (emoji, color); restrained — each fires once and sections are far apart so
# the 2–3-color discipline still holds visually. Match by title prefix.
CALLOUT_SECTIONS = {
    "一句话总结": ("💡", "blue"),
    "毒舌评论": ("🔴", "red"),
    "核心直觉": ("✨", "purple"),
    "最脆弱的假设": ("❗", "orange"),
    "我的判断": ("✅", "green"),
    "后续研究设想": ("🚀", "purple"),
}


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text):
    """Convert inline markdown to DocxXML inline tags, escaping literal text.

    Order: protect code/latex/link spans as placeholders, apply bold on the
    remainder, escape literals, then restore placeholders.
    """
    text = CONTROL_TAGS.sub("", text)   # drop figure directives ([p.N]/[hero]/[@...])
    slots = []

    def stash(html):
        slots.append(html)
        return f"\x00{len(slots) - 1}\x00"

    # Semantic color first, recursing so a colored term can also be bold/code.
    text = COLOR.sub(
        lambda m: stash(f'<span text-color="{CMAP[m.group(1)]}">{inline(m.group(2))}</span>'),
        text)
    text = LINK.sub(lambda m: stash(f'<a href="{esc(m.group(2))}">{esc(m.group(1))}</a>'), text)
    text = INLINE_CODE.sub(lambda m: stash(f"<code>{esc(m.group(1))}</code>"), text)
    # $$...$$ display and $...$ inline both map to Feishu's inline <latex>.
    text = DISPLAY_LATEX.sub(lambda m: stash(f"<latex>{esc(m.group(1).strip())}</latex>"), text)
    text = INLINE_LATEX.sub(lambda m: stash(f"<latex>{esc(m.group(1))}</latex>"), text)
    text = BOLD.sub(lambda m: stash(f"<b>{esc(m.group(1))}</b>"), text)
    # escape whatever literal text remains (placeholders use \x00 sentinels)
    out = "".join(p if p.startswith("\x00") else esc(p) for p in re.split(r"(\x00\d+\x00)", text))
    # restore placeholders, looping so nested ones (e.g. color inside bold) fully resolve
    while "\x00" in out:
        out = re.sub(r"\x00(\d+)\x00", lambda m: slots[int(m.group(1))], out)
    return out


def _disp_width(t):
    """Rough display width: CJK/full-width counts as 2, others 1."""
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in t)


def _plain_cell(t):
    """Strip note markup so a cell can be measured / alignment-detected."""
    t = re.sub(r"\{\{[bpogr]:(.+?)\}\}", r"\1", t)
    return t.replace("**", "").replace("`", "").replace("$", "").strip()


def parse_table(lines, i):
    """Parse a GFM pipe table -> DocxXML with content-proportional column widths
    and centered numeric columns. Returns (xml, next_i)."""
    def cells(row):
        # split on unescaped | ; restore \| as a literal | inside cells
        return [c.strip().replace("\\|", "|")
                for c in re.split(r"(?<!\\)\|", row.strip().strip("|"))]
    head = cells(lines[i])
    ncol = len(head)
    body_rows = []
    i += 2  # skip header + separator
    while i < len(lines) and TABLE_ROW.match(lines[i]):
        body_rows.append(cells(lines[i]))
        i += 1

    def col(j):  # all plain cell texts in column j (header + body)
        out = [_plain_cell(head[j])]
        out += [_plain_cell(r[j]) for r in body_rows if j < len(r)]
        return out

    # Column widths ∝ widest cell (capped so one long prose cell can't starve the rest).
    weights = [min(40, max((_disp_width(x) for x in col(j)), default=1)) for j in range(ncol)]
    tot = sum(weights) or 1
    widths = [max(64, round(w / tot * 820)) for w in weights]
    # Center a column only if every body cell is short and contains a digit (number cols).
    aligns = []
    for j in range(ncol):
        body = [_plain_cell(r[j]) for r in body_rows if j < len(r)]
        center = bool(body) and all(_disp_width(x) <= 8 and any(c.isdigit() for c in x)
                                    for x in body)
        aligns.append("center" if center else "left")

    def wrap(content, j):
        return f'<p align="center">{content}</p>' if aligns[j] == "center" else content

    thead = "<tr>" + "".join(
        f'<th background-color="light-gray">{wrap(f"<b>{inline(head[j])}</b>", j)}</th>'
        for j in range(ncol)) + "</tr>"
    tbody = "".join(
        "<tr>" + "".join(f"<td>{wrap(inline(r[j]), j)}</td>" for j in range(len(r))) + "</tr>"
        for r in body_rows)
    colgroup = "<colgroup>" + "".join(f'<col width="{w}"/>' for w in widths) + "</colgroup>"
    return f"<table>{colgroup}<thead>{thead}</thead><tbody>{tbody}</tbody></table>", i


def render_blocks(lines):
    """Render a list of markdown lines (no `##` section headings) to DocxXML."""
    out = []
    i = 0
    list_buf = []      # (indent, text)
    list_type = None   # 'ul' | 'ol'

    def flush_list():
        nonlocal list_buf, list_type
        if not list_buf:
            return
        tag = list_type
        attr = ' seq="auto"' if tag == "ol" else ""
        # one level of nesting: indent >= 2 spaces -> child list inside prev <li>
        html = f"<{tag}{attr}>"
        prev_nested = False
        for indent, txt in list_buf:
            if indent >= 2:
                if not prev_nested:
                    html = html[:-5] if html.endswith("</li>") else html  # reopen last li
                    html += f"<{tag}{attr}><li>{inline(txt)}</li>"
                    prev_nested = True
                else:
                    html += f"<li>{inline(txt)}</li>"
            else:
                if prev_nested:
                    html += f"</{tag}></li>"
                    prev_nested = False
                html += f"<li>{inline(txt)}</li>"
        if prev_nested:
            html += f"</{tag}></li>"
        html += f"</{tag}>"
        out.append(html)
        list_buf = []
        list_type = None

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):  # fenced code block
            flush_list()
            lang = ln[3:].strip() or "text"
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            out.append(f'<pre lang="{esc(lang)}"><code>{esc(chr(10).join(buf))}</code></pre>')
            i += 1
            continue
        if TABLE_ROW.match(ln) and i + 1 < len(lines) and TABLE_SEP.match(lines[i + 1]):
            flush_list()
            xml, i = parse_table(lines, i)
            out.append(xml)
            continue
        if ln.startswith("###### "):
            flush_list(); out.append(f"<h6>{inline(ln[7:].strip())}</h6>")
        elif ln.startswith("##### "):
            flush_list(); out.append(f"<h5>{inline(ln[6:].strip())}</h5>")
        elif ln.startswith("#### "):
            flush_list(); out.append(f"<h4>{inline(ln[5:].strip())}</h4>")
        elif ln.startswith("### "):
            flush_list(); out.append(f"<h3>{inline(ln[4:].strip())}</h3>")
        elif ORDERED.match(ln):
            indent = len(ln) - len(ln.lstrip(" "))
            if list_type == "ul":
                flush_list()
            list_type = "ol"
            list_buf.append((indent, ORDERED.sub("", ln)))
        elif re.match(r"^\s*-\s+", ln):
            indent = len(ln) - len(ln.lstrip(" "))
            if list_type == "ol":
                flush_list()
            list_type = "ul"
            list_buf.append((indent, re.sub(r"^\s*-\s+", "", ln)))
        elif ln.strip() == "---":
            flush_list(); out.append("<hr/>")
        elif ln.strip() == "":
            flush_list()
        else:
            flush_list(); out.append(f"<p>{inline(ln.strip())}</p>")
        i += 1
    flush_list()
    return "".join(out)


def lint_xml(xml):
    """Catch malformed render output so broken docs never ship (fail loud).

    Covers the failure classes the markup can silently produce: leftover
    `{{`/`}}` (nested or mistyped color tags — color tags must NOT nest),
    residual \\x00 placeholders (inline restore failed), and unbalanced
    inline/style tags.
    """
    problems = []
    # An unconsumed `{{c:` opener means a color tag failed to parse (nested or
    # mistyped). Match the opener specifically — bare `{{`/`}}` occur in valid
    # LaTeX (e.g. V_{\text{vae}}^{\text{clean}}) and must not false-positive.
    m = re.search(r"\{\{[bpogr]:", xml)
    if m:
        ctx = xml[max(0, m.start() - 30):m.start() + 30].replace("\n", " ")
        problems.append(f"未解析的颜色标记（颜色标记不可嵌套）: …{ctx}…")
    if "\x00" in xml:
        problems.append("残留占位符 \\x00：inline() 还原失败")
    for tag in ("span", "b", "callout", "latex", "table", "td", "li"):
        o = len(re.findall(rf"<{tag}[ >]", xml))
        c = len(re.findall(rf"</{tag}>", xml))
        if o != c:
            problems.append(f"标签不平衡 <{tag}>：{o} 开 / {c} 闭")
    big = [b for b in top_level_blocks(xml) if len(b) > HARD_BLOCK]
    if big:
        problems.append(f"单个块过长（{len(big[0])}>{HARD_BLOCK}），无法安全分块发布——"
                        f"把该小节拆出子标题/拆段：…{big[0][:50]}…")
    return problems


def lint_anchors(body_xml, inline_figs):
    """Each inline figure's [@anchor] must match exactly one block's text, or the
    figure silently lands at the doc end instead of inline."""
    problems = []
    text = re.sub(r"<[^>]+>", "", body_xml)   # strip tags -> rendered text
    for m in inline_figs:
        n = text.count(m["anchor"])
        if n == 0:
            problems.append(f"图 {m['label']} 的锚点未在正文出现：'{m['anchor']}'（图会落到文末）")
        elif n > 1:
            problems.append(f"图 {m['label']} 的锚点不唯一（出现 {n} 次）：'{m['anchor']}'（可能插错位置）")
    return problems


def lint_md_tables(md):
    """Flag GFM table rows whose column count differs from the header — usually a
    stray unescaped `|` inside a cell (use `\\|`)."""
    problems = []
    lines = md.splitlines()
    for i, ln in enumerate(lines):
        if TABLE_ROW.match(ln) and i + 1 < len(lines) and TABLE_SEP.match(lines[i + 1]):
            ncol = len(re.split(r"(?<!\\)\|", ln.strip().strip("|")))
            j = i + 2
            while j < len(lines) and TABLE_ROW.match(lines[j]):
                rc = len(re.split(r"(?<!\\)\|", lines[j].strip().strip("|")))
                if rc != ncol:
                    problems.append(f"表格列数不一致（表头 {ncol}，第 {j+1} 行 {rc}）：可能有未转义的 | ，"
                                    f"用 \\| ：{lines[j].strip()[:40]}")
                j += 1
    return problems


def split_sections(md):
    """Split a note into (doc_title, [(section_title, [body_lines]), ...])."""
    title = "Untitled"
    sections = []
    cur_title, cur_body = None, []
    for ln in md.splitlines():
        if ln.startswith("# ") and not ln.startswith("## ") and title == "Untitled":
            title = ln[2:].strip()
        elif ln.startswith("## "):
            if cur_title is not None:
                sections.append((cur_title, cur_body))
            cur_title, cur_body = ln[3:].strip(), []
        elif cur_title is not None:
            cur_body.append(ln)
    if cur_title is not None:
        sections.append((cur_title, cur_body))
    return title, sections


def callout(emoji, color, inner):
    return (f'<callout emoji="{emoji}" background-color="light-{color}" '
            f'border-color="{color}">{inner}</callout>')


def h2(title, color="blue"):
    """Bold colored section heading (<b> outside <span> per the XML nesting order)."""
    return f'<h2><b><span text-color="{color}">{inline(title)}</span></b></h2>'


def render_metadata(body):
    """Render the Metadata bullet block as a clean 2-column table."""
    rows = []
    for ln in body:
        m = re.match(r"^- ([^:：]+)[:：]\s*(.*)$", ln.strip())
        if m and m.group(2):
            rows.append((m.group(1).strip(), m.group(2).strip()))
    if not rows:
        return render_blocks(body)
    cells = "".join(
        f'<tr><td background-color="light-gray"><b>{inline(k)}</b></td>'
        f"<td>{inline(v)}</td></tr>" for k, v in rows)
    # colgroup widths make the table span the page (narrow field col + wide value col).
    return ('<table><colgroup><col width="170"/><col width="640"/></colgroup>'
            f"<tbody>{cells}</tbody></table>")


def render_grid_pair(left, right):
    """Render two sections side-by-side: Strengths (green) | Limitations (orange)."""
    lt, lb = left
    rt, rb = right
    lcol = callout("✅", "green", f"<p><b>{inline(lt)}</b></p>" + render_blocks(lb))
    rcol = callout("🚧", "orange", f"<p><b>{inline(rt)}</b></p>" + render_blocks(rb))
    return (f'<h2><b><span text-color="green">{inline(lt)}</span>'
            f' / <span text-color="orange">{inline(rt)}</span></b></h2>'
            f'<grid><column width-ratio="0.5">{lcol}</column>'
            f'<column width-ratio="0.5">{rcol}</column></grid>')


def match_callout(section_title):
    for key, style in CALLOUT_SECTIONS.items():
        if section_title.startswith(key):
            return style
    return None


def md_to_docx_xml(md):
    """Convert a marginalia note to DocxXML with semantic block routing.

    Returns (doc_title, xml_blocks). Signature sections (TL;DR, 毒舌评论, …) are
    wrapped in colored callouts; Strengths/Limitations become a side-by-side grid;
    Metadata renders as a table; everything else is plain structural blocks.
    """
    title, sections = split_sections(md)
    out = []
    i = 0
    while i < len(sections):
        sect_title, body = sections[i]
        # Pair Strengths + Limitations into a two-column grid.
        if (sect_title.startswith("优势") and i + 1 < len(sections)
                and sections[i + 1][0].startswith("局限")):
            out.append(render_grid_pair(sections[i], sections[i + 1]))
            i += 2
            continue
        if sect_title.startswith("元数据"):
            out.append(f"{h2(sect_title)}{render_metadata(body)}")
            i += 1
            continue
        style = match_callout(sect_title)
        if style:
            emoji, color = style
            out.append(f"{h2(sect_title, color)}{callout(emoji, color, render_blocks(body))}")
        else:
            out.append(f"{h2(sect_title)}{render_blocks(body)}")
        i += 1
    # Divider between sections for visual rhythm (Metadata header sits above the first).
    return title, "\n<hr/>\n".join(out)


# ---------------------------------------------------------------- note parsing

def parse_metadata(md):
    """Pull the `## Metadata` bullet block into a dict {field: value}."""
    meta = {}
    m = re.search(r"^## 元数据.*?$(.*?)^## ", md, re.S | re.M)
    block = m.group(1) if m else ""
    for line in block.splitlines():
        mm = re.match(r"^- ([^:：]+)[:：]\s*(.*)$", line.strip())
        if mm:
            meta[mm.group(1).strip()] = mm.group(2).strip()
    return meta


FIG_TAG = re.compile(
    r"(Fig\.?|Figure|Table)\s*(\d+)\s*\[p\.(\d+)\]\s*"
    r"(\[hero\])?\s*(\[@[^\]]+\])?\s*(\[box=[\d.,\s]+\])?\s*(.*)$")


def _clean_caption(text):
    """Strip note markup ({{c:..}}, **bold**, `code`, $latex$) for a clean caption."""
    text = re.sub(r"\{\{[bpogr]:(.+?)\}\}", r"\1", text)
    text = text.replace("**", "").replace("`", "").replace("$", "")
    return text.strip().lstrip("：:").strip()


def parse_figures(md):
    """Parse `Fig.N [p.P] [hero] [@anchor] 描述` tags from Key Artifacts bullets.

    Returns deduped [{label, page, hero, anchor, caption}, ...]. `caption` is the
    描述 after the tag (prefixed 图N/表N); `anchor` (from `[@文本]`) places the
    figure inline after the block matching that text, else it lands in 图表 section.
    """
    found, seen = [], set()
    for line in md.splitlines():
        m = FIG_TAG.search(line)
        if not m:
            continue
        kind = "Table" if m.group(1).lower().startswith("table") else "Figure"
        num = m.group(2)
        if (kind, num) in seen:
            continue
        seen.add((kind, num))
        anchor = m.group(5)[2:-1].strip() if m.group(5) else None
        box = None
        if m.group(6):
            nums = [float(v) for v in re.findall(r"[\d.]+", m.group(6))]
            box = nums[:4] if len(nums) >= 4 else None
        desc = _clean_caption(m.group(7))
        prefix = ("表" if kind == "Table" else "图") + num
        found.append({
            "label": f"{kind} {num}", "page": int(m.group(3)),
            "hero": bool(m.group(4)), "anchor": anchor, "box": box,
            "caption": f"{prefix} {desc}" if desc else f"{kind} {num}",
        })
    return found


# ---------------------------------------------------------------- lark-cli

def lark(*args, inp=None):
    """Run lark-cli; return the unwrapped `data` payload (raises on failure).

    lark-cli wraps results as {"ok":bool, "data":{...}, "_notice":...}. We
    surface `data` to callers; auth-status and other unwrapped shapes pass through.
    """
    r = subprocess.run(["lark-cli", *args], capture_output=True, text=True, input=inp)
    if r.returncode != 0:
        raise RuntimeError(f"lark-cli {' '.join(args)} failed:\n{r.stderr or r.stdout}")
    # Some commands print human progress lines before the JSON payload; slice it out.
    out = r.stdout
    lo, hi = out.find("{"), out.rfind("}")
    try:
        parsed = json.loads(out[lo:hi + 1] if lo >= 0 else out)
    except json.JSONDecodeError:
        return out
    if isinstance(parsed, dict):
        if parsed.get("ok") is False:
            raise RuntimeError(f"lark-cli {' '.join(args)} returned error:\n{parsed}")
        return parsed.get("data", parsed)
    return parsed


def auth_precheck():
    st = lark("auth", "status")
    user = (st or {}).get("identities", {}).get("user", {}) if isinstance(st, dict) else {}
    if not user.get("available"):
        sys.exit("未登录飞书用户身份。请先运行：\n  lark-cli auth login --scope "
                 '"docs:document.content:read docx:document:create docx:document:write_only '
                 'docs:document.media:upload wiki:node:create wiki:space:write_only '
                 'base:table:create base:record:create base:record:update drive:file:upload"')
    return user


# ---------------------------------------------------------------- mapping / config

CFG_PATH = Path(".marginalia/feishu.json")
SPACE_NAME = "marginalia 论文精读"
BASE_NAME = "marginalia 论文索引"
BASE_FIELDS = [
    {"name": "Title", "type": "text"}, {"name": "Authors", "type": "text"},
    {"name": "Venue", "type": "text"}, {"name": "Year", "type": "number"},
    {"name": "Domain", "type": "text"}, {"name": "Tags", "type": "text"},
    {"name": "Status", "type": "text"}, {"name": "Paper", "type": "text"},
    {"name": "Feishu", "type": "text"}, {"name": "Note", "type": "text"},
]


def load_cfg():
    if CFG_PATH.exists():
        return json.loads(CFG_PATH.read_text(encoding="utf-8"))
    return {"wiki_space_id": None, "domain_nodes": {}, "base_token": None,
            "table_id": None, "notes": {}}


def save_cfg(cfg):
    CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def dig(d, *keys):
    """First non-empty value among nested key paths, e.g. dig(r,'space','space_id')."""
    for k in keys:
        cur = d
        for part in (k if isinstance(k, tuple) else (k,)):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur:
            return cur
    return None


def ensure_space(cfg):
    """Resolve the target wiki space. Creating a dedicated shared space needs
    org admin permission, so default to the personal library `my_library`.
    """
    if cfg.get("wiki_space_id"):
        return cfg["wiki_space_id"]
    try:
        r = lark("wiki", "+space-create", "--name", SPACE_NAME, "--as", "user")
        cfg["wiki_space_id"] = dig(r, ("space", "space_id"), "space_id")
        print(f"created wiki space: {cfg['wiki_space_id']}")
    except Exception as e:  # noqa: BLE001 - fall back to personal library
        print(f"note: cannot create shared space ({e.__class__.__name__}); using my_library",
              file=sys.stderr)
        cfg["wiki_space_id"] = "my_library"
    save_cfg(cfg)
    return cfg["wiki_space_id"]


def ensure_domain_node(cfg, domain):
    if domain in cfg.get("domain_nodes", {}):
        return cfg["domain_nodes"][domain]
    space = ensure_space(cfg)
    r = lark("wiki", "+node-create", "--space-id", space, "--obj-type", "docx",
             "--title", f"{domain}", "--as", "user")
    tok = dig(r, "node_token", ("node", "node_token"))
    if r.get("resolved_space_id"):   # my_library resolves to a concrete space id
        cfg["wiki_space_id"] = r["resolved_space_id"]
    cfg.setdefault("domain_nodes", {})[domain] = tok
    save_cfg(cfg)
    print(f"created domain node {domain}: {tok}")
    return tok


def ensure_base(cfg):
    if cfg.get("base_token") and cfg.get("table_id"):
        return cfg["base_token"], cfg["table_id"]
    r = lark("base", "+base-create", "--name", BASE_NAME, "--table-name", "Papers",
             "--fields", json.dumps(BASE_FIELDS, ensure_ascii=False), "--as", "user")
    bt = dig(r, ("base", "base_token"), "base_token", ("app", "app_token"))
    # The created table id isn't cleanly in the create response; resolve it.
    tl = lark("base", "+table-list", "--base-token", bt, "--as", "user")
    tables = tl.get("tables") or tl.get("items") or []
    tid = (tables[0].get("id") or tables[0].get("table_id")) if tables else None
    cfg["base_token"], cfg["table_id"] = bt, tid
    save_cfg(cfg)
    print(f"created base: {bt} / table {tid}")
    return bt, tid


# ---------------------------------------------------------------- record / writeback

def build_record(meta, domain, note_rel, doc_url):
    venue = meta.get("Venue / Year", "")
    ym = re.search(r"(19|20)\d{2}", venue + " " + meta.get("Note Name", ""))
    return {
        "Title": meta.get("Title", ""), "Authors": meta.get("Authors", ""),
        "Venue": venue, "Year": int(ym.group(0)) if ym else None,
        "Domain": domain, "Tags": meta.get("Tags", ""),
        "Status": meta.get("Status", ""), "Paper": meta.get("Paper", ""),
        "Feishu": doc_url, "Note": note_rel,
    }


def find_record_id(bt, tid, note_rel):
    """Look up a Base record id by its unique Note path (keeps the index idempotent).

    record-list --format json returns rows as value-lists in `data`, ids in the
    parallel `record_id_list`, and column order in `fields` (Feishu may reorder
    columns, so the Note column index must be read, not assumed).
    """
    try:
        D = lark("base", "+record-list", "--base-token", bt, "--table-id", tid,
                 "--format", "json", "--as", "user")
    except Exception:  # noqa: BLE001
        return None
    recs, ids = D.get("data") or [], D.get("record_id_list") or []
    names = [f if isinstance(f, str) else (f.get("name") or f.get("field_name"))
             for f in (D.get("fields") or [])]
    if "Note" not in names:
        return None
    ci = names.index("Note")
    for i, row in enumerate(recs):
        if isinstance(row, list) and ci < len(row) and row[ci] == note_rel and i < len(ids):
            return ids[i]
    return None


def content_hash(md):
    """Stable hash of the note, ignoring the auto-written Feishu Doc line."""
    norm = re.sub(r"^- Feishu Doc:.*$\n?", "", md, flags=re.M)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def writeback_url(note_path, md, doc_url):
    line = f"- Feishu Doc: {doc_url}"
    if re.search(r"^- Feishu Doc:.*$", md, flags=re.M):
        md = re.sub(r"^- Feishu Doc:.*$", line, md, flags=re.M)
    else:  # insert right after the Paper: line in Metadata
        md = re.sub(r"^(- Paper:.*$)", r"\1\n" + line, md, count=1, flags=re.M)
    note_path.write_text(md, encoding="utf-8")
    return md


SEP = "\n<hr/>\n"
MAX_CHUNK = 3000   # `docs +create`/`append` truncate on oversized --content; chunk under this
HARD_BLOCK = 8000  # a single atomic block above this can't be chunked safely -> lint fails

_TAG = re.compile(r"<(/?)([a-zA-Z0-9]+)\b[^>]*?(/?)>")


def top_level_blocks(xml):
    """Split xml into top-level block strings via a tag-depth scan (so a chunk
    boundary never lands inside a callout/grid/table/list). Contiguous spans —
    joining them reconstructs xml exactly."""
    blocks, depth, start = [], 0, 0
    for m in _TAG.finditer(xml):
        closing, _, selfclose = m.group(1), m.group(2), m.group(3)
        if selfclose:
            if depth == 0:
                blocks.append(xml[start:m.end()]); start = m.end()
        elif not closing:
            depth += 1
        else:
            depth = max(0, depth - 1)
            if depth == 0:
                blocks.append(xml[start:m.end()]); start = m.end()
    if start < len(xml):
        blocks.append(xml[start:])
    return [b for b in blocks if b.strip()]


def chunk_body(body_xml):
    """Group top-level blocks into chunks under MAX_CHUNK. No separator is added
    on join (the `<hr/>` dividers are already blocks), so an oversized section
    splitting across chunks won't sprout a spurious divider mid-section."""
    chunks, cur = [], ""
    for b in top_level_blocks(body_xml):
        if cur and len(cur) + len(b) > MAX_CHUNK:
            chunks.append(cur); cur = ""
        cur += b
    if cur:
        chunks.append(cur)
    return chunks or [""]


def _insert_media(did, m, *, width=None, anchor=None, before=False):
    args = ["docs", "+media-insert", "--doc", did, "--file", m["path"],
            "--caption", m.get("caption", m["label"]), "--align", "center", "--as", "user"]
    if width:
        args += ["--width", str(width)]
    if anchor:
        args += ["--selection-with-ellipsis", anchor]
        if before:
            args += ["--before"]
    lark(*args)


def build_doc_body(title, body_xml, hero, inline_figs, end_figs, hero_anchor, doc_id=None):
    """Build/refresh the doc body. If doc_id is given, overwrite it in place
    (stable URL); otherwise create a new doc. Oversized --content is silently
    truncated, so write the title + first chunk, then `append` the rest.
    """
    chunks = chunk_body(body_xml)
    head = f"<title>{esc(title)}</title>\n{chunks[0]}"
    if doc_id:
        lark("docs", "+update", "--api-version", "v2", "--doc", doc_id,
             "--command", "overwrite", "--content", "-", "--as", "user", inp=head)
        did, url = doc_id, None
    else:
        doc = lark("docs", "+create", "--content", "-", "--as", "user", inp=head)["document"]
        did, url = doc["document_id"], doc["url"]
    for ch in chunks[1:]:  # boundaries are between blocks; no separator to add
        lark("docs", "+update", "--api-version", "v2", "--doc", did,
             "--command", "append", "--content", ch, "--as", "user")
    if len(chunks) > 1:
        print(f"  body {'overwritten' if doc_id else 'created'} in {len(chunks)} chunks")
    # Hero banner above the first section; inline figures after their anchor text;
    # the rest appended under the 图表 section. media-insert falls back to append.
    if hero and hero_anchor:
        try:
            _insert_media(did, hero, width=720, anchor=hero_anchor, before=True)
            print(f"  hero {hero['label']} -> top")
        except Exception as e:  # noqa: BLE001
            print(f"WARN hero insert failed ({e.__class__.__name__}); appending", file=sys.stderr)
            end_figs = [hero] + end_figs
    for m in inline_figs:
        try:
            _insert_media(did, m, anchor=m["anchor"])
            print(f"  inserted {m['label']} @ '{m['anchor'][:18]}'")
        except Exception as e:  # noqa: BLE001
            print(f"WARN inline insert {m['label']} failed ({e.__class__.__name__}); appending",
                  file=sys.stderr)
            end_figs.append(m)
    for m in end_figs:
        _insert_media(did, m)
        print(f"  inserted {m['label']}")
    return did, url


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("note", help="path to the md note")
    ap.add_argument("--pdf", help="source PDF for figures (else figures skipped)")
    ap.add_argument("--dry-run", action="store_true", help="build XML, don't call lark-cli")
    ap.add_argument("--force", action="store_true", help="republish even if unchanged")
    args = ap.parse_args()

    note_path = Path(args.note)
    md = note_path.read_text(encoding="utf-8")
    note_rel = str(note_path)
    domain = note_path.parent.name if note_path.parent.name != "notes" else "general"
    title, body_xml = md_to_docx_xml(md)
    meta = parse_metadata(md)
    figs = parse_figures(md) if args.pdf else []
    _, sections = split_sections(md)
    hero_anchor = sections[0][0] if sections else None   # first section heading text

    fig_dir = Path(".marginalia/figs") / note_path.stem   # relative: lark needs cwd-relative paths
    fig_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for f in figs:
        try:
            m = ef.crop_artifact(args.pdf, f["page"], f["label"], fig_dir, box=f.get("box"))
            m.update(caption=f["caption"], anchor=f["anchor"], hero=f["hero"])
            manifest.append(m)
        except Exception as e:  # noqa: BLE001
            print(f"WARN figure {f['label']}@{f['page']}: {e}", file=sys.stderr)
    # hero banners the top; figures with an [@anchor] go inline; the rest land in 图表.
    hero = next((m for m in manifest if m.get("hero")), None)
    inline_figs = [m for m in manifest if not m.get("hero") and m.get("anchor")]
    end_figs = [m for m in manifest if not m.get("hero") and not m.get("anchor")]
    if end_figs:
        body_xml += SEP + h2("图表 (Figures)")

    problems = lint_xml(body_xml) + lint_anchors(body_xml, inline_figs) + lint_md_tables(md)
    if problems:
        for p in problems:
            print(f"LINT: {p}", file=sys.stderr)

    if args.dry_run:
        print(f"<title>{esc(title)}</title>\n{body_xml}")
        print(f"\n--- hero={hero['label'] if hero else None}; "
              f"inline={[(m['label'], m['anchor']) for m in inline_figs]}; "
              f"end={[m['label'] for m in end_figs]}; lint={'OK' if not problems else 'FAIL'} ---",
              file=sys.stderr)
        return

    if problems:
        sys.exit("渲染校验未通过，已中止发布（修好上面 LINT 指出的标记问题再发）。")

    auth_precheck()
    cfg = load_cfg()
    prev = cfg["notes"].get(note_rel)
    h = content_hash(md)
    if prev and prev.get("hash") == h and not args.force:
        print(f"unchanged, skipping: {prev.get('url')}")
        return

    # In-place update keeps the URL stable: reuse the existing doc via `overwrite`.
    # Only create (and file into Wiki) on first publish or if the old doc is gone.
    node_token = prev.get("node_token") if prev else None
    doc_id = doc_url = None
    if prev and prev.get("doc_id"):
        try:
            doc_id, _ = build_doc_body(title, body_xml, hero, inline_figs, end_figs,
                                       hero_anchor, doc_id=prev["doc_id"])
            doc_url = prev.get("url")
            print(f"updated in place: {doc_url}")
        except Exception as e:  # noqa: BLE001
            print(f"WARN in-place update failed ({e.__class__.__name__}); creating fresh",
                  file=sys.stderr)
            doc_id = None
    if not doc_id:
        doc_id, doc_url = build_doc_body(title, body_xml, hero, inline_figs, end_figs, hero_anchor)
        print(f"doc: {doc_url}")
        # File the new doc under the Wiki domain node, capturing its node token.
        node = ensure_domain_node(cfg, domain)
        space = cfg["wiki_space_id"]
        node_token = None
        try:
            mv = lark("wiki", "+move", "--obj-token", doc_id, "--obj-type", "docx",
                      "--target-space-id", space, "--target-parent-token", node, "--as", "user")
            node_token = dig(mv, "node_token", ("node", "node_token"))
            print(f"moved into wiki/{domain}")
        except Exception as e:  # noqa: BLE001
            print(f"WARN wiki move failed: {e}", file=sys.stderr)
        if not node_token:                           # resolve via node-list by obj_token
            try:
                nl = lark("wiki", "+node-list", "--space-id", str(space),
                          "--parent-node-token", node, "--as", "user")
                for it in (nl.get("nodes") or []):
                    if it.get("obj_token") == doc_id:
                        node_token = it.get("node_token")
                        break
            except Exception:  # noqa: BLE001
                pass

    # Upsert the Base index row.
    bt, tid = ensure_base(cfg)
    rec = build_record(meta, domain, note_rel, doc_url)
    rec_json = json.dumps({k: v for k, v in rec.items() if v is not None}, ensure_ascii=False)
    rec_id = (prev.get("record_id") if prev else None) or find_record_id(bt, tid, note_rel)
    rargs = ["base", "+record-upsert", "--base-token", bt, "--table-id", tid,
             "--json", rec_json, "--format", "json", "--as", "user"]
    if rec_id:
        rargs += ["--record-id", rec_id]
    lark(*rargs)
    if not rec_id:                                  # upsert response omits the id; look it up
        rec_id = find_record_id(bt, tid, note_rel)
    print(f"base row upserted ({rec_id})")

    # Write the Feishu URL back into the note, then record the mapping.
    writeback_url(note_path, md, doc_url)
    cfg["notes"][note_rel] = {"doc_id": doc_id, "url": doc_url, "node_token": node_token,
                              "record_id": rec_id, "hash": h}
    save_cfg(cfg)
    print(json.dumps({"doc": doc_url, "figures": len(manifest),
                      "wiki": f"{domain}", "base_record": rec_id}, ensure_ascii=False))


if __name__ == "__main__":
    main()
