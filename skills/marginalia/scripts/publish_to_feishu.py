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
INLINE_LATEX = re.compile(r"\$([^$]+)\$")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text):
    """Convert inline markdown to DocxXML inline tags, escaping literal text.

    Order: protect code/latex/link spans as placeholders, apply bold on the
    remainder, escape literals, then restore placeholders.
    """
    slots = []

    def stash(html):
        slots.append(html)
        return f"\x00{len(slots) - 1}\x00"

    text = LINK.sub(lambda m: stash(f'<a href="{esc(m.group(2))}">{esc(m.group(1))}</a>'), text)
    text = INLINE_CODE.sub(lambda m: stash(f"<code>{esc(m.group(1))}</code>"), text)
    text = INLINE_LATEX.sub(lambda m: stash(f"<latex>{esc(m.group(1))}</latex>"), text)
    text = BOLD.sub(lambda m: stash(f"<b>{esc(m.group(1))}</b>"), text)
    # escape whatever literal text remains (placeholders use \x00 sentinels)
    out = "".join(p if p.startswith("\x00") else esc(p) for p in re.split(r"(\x00\d+\x00)", text))
    return re.sub(r"\x00(\d+)\x00", lambda m: slots[int(m.group(1))], out)


def md_to_docx_xml(md):
    """Convert a marginalia note body to DocxXML. Returns (title, xml_blocks)."""
    lines = md.splitlines()
    title = "Untitled"
    out = []
    i = 0
    list_buf = []  # (indent, text)

    def flush_list():
        nonlocal list_buf
        if not list_buf:
            return
        # one level of nesting: indent >= 2 spaces -> child <ul> inside prev <li>
        html = "<ul>"
        prev_nested = False
        for indent, txt in list_buf:
            if indent >= 2:
                if not prev_nested:
                    html = html[:-5] if html.endswith("</li>") else html  # reopen last li
                    html += f"<ul><li>{inline(txt)}</li>"
                    prev_nested = True
                else:
                    html += f"<li>{inline(txt)}</li>"
            else:
                if prev_nested:
                    html += "</ul></li>"
                    prev_nested = False
                html += f"<li>{inline(txt)}</li>"
        if prev_nested:
            html += "</ul></li>"
        html += "</ul>"
        out.append(html)
        list_buf = []

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
            code = esc("\n".join(buf))
            out.append(f'<pre lang="{esc(lang)}"><code>{code}</code></pre>')
            i += 1
            continue
        if ln.startswith("# "):
            flush_list()
            title = ln[2:].strip()
        elif ln.startswith("###### "):
            flush_list(); out.append(f"<h6>{inline(ln[7:].strip())}</h6>")
        elif ln.startswith("##### "):
            flush_list(); out.append(f"<h5>{inline(ln[6:].strip())}</h5>")
        elif ln.startswith("#### "):
            flush_list(); out.append(f"<h4>{inline(ln[5:].strip())}</h4>")
        elif ln.startswith("### "):
            flush_list(); out.append(f"<h3>{inline(ln[4:].strip())}</h3>")
        elif ln.startswith("## "):
            flush_list(); out.append(f"<h2>{inline(ln[3:].strip())}</h2>")
        elif re.match(r"^\s*-\s+", ln):
            indent = len(ln) - len(ln.lstrip(" "))
            txt = re.sub(r"^\s*-\s+", "", ln)
            list_buf.append((indent, txt))
        elif ln.strip() == "---":
            flush_list(); out.append("<hr/>")
        elif ln.strip() == "":
            flush_list()
        else:
            flush_list(); out.append(f"<p>{inline(ln.strip())}</p>")
        i += 1
    flush_list()
    return title, "\n".join(out)


# ---------------------------------------------------------------- note parsing

def parse_metadata(md):
    """Pull the `## Metadata` bullet block into a dict {field: value}."""
    meta = {}
    m = re.search(r"^## Metadata\s*$(.*?)^## ", md, re.S | re.M)
    block = m.group(1) if m else ""
    for line in block.splitlines():
        mm = re.match(r"^- ([^:：]+)[:：]\s*(.*)$", line.strip())
        if mm:
            meta[mm.group(1).strip()] = mm.group(2).strip()
    return meta


def parse_figures(md):
    """Find `Fig.N [p.P]` / `Figure N [p.P]` tags -> [(label, page), ...] (deduped)."""
    found, seen = [], set()
    for m in re.finditer(r"(?:Fig\.?|Figure|Table)\s*(\d+)\s*\[p\.(\d+)\]", md):
        kind = "Table" if md[m.start():m.start() + 5].lower().startswith("table") else "Figure"
        key = (kind, m.group(1))
        if key not in seen:
            seen.add(key)
            found.append((f"{kind} {m.group(1)}", int(m.group(2))))
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
    names = [f.get("name") or f.get("field_name") for f in (D.get("fields") or [])]
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


def build_doc_with_figures(title, body_xml, manifest):
    xml = f"<title>{esc(title)}</title>\n{body_xml}"
    res = lark("docs", "+create", "--content", "-", "--as", "user", inp=xml)
    doc = res["document"]
    for m in manifest:
        lark("docs", "+media-insert", "--doc", doc["document_id"], "--file", m["path"],
             "--caption", m["label"], "--align", "center", "--as", "user")
        print(f"  inserted {m['label']}")
    return doc["document_id"], doc["url"]


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

    fig_dir = Path(".marginalia/figs") / note_path.stem   # relative: lark needs cwd-relative paths
    fig_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    if figs and args.pdf:
        body_xml += "\n<h2>图表 Figures</h2>"
        for label, page in figs:
            try:
                manifest.append(ef.crop_artifact(args.pdf, page, label, fig_dir))
            except Exception as e:  # noqa: BLE001
                print(f"WARN figure {label}@{page}: {e}", file=sys.stderr)

    if args.dry_run:
        print(f"<title>{esc(title)}</title>\n{body_xml}")
        print(f"\n--- {len(manifest)} figures ---", file=sys.stderr)
        for m in manifest:
            print(f"  {m['label']}  {m['width']}x{m['height']}  {m['path']}", file=sys.stderr)
        return

    auth_precheck()
    cfg = load_cfg()
    prev = cfg["notes"].get(note_rel)
    h = content_hash(md)
    if prev and prev.get("hash") == h and not args.force:
        print(f"unchanged, skipping: {prev.get('url')}")
        return

    # (Re)create the doc. On change, best-effort delete the stale doc first.
    if prev and prev.get("doc_id"):
        try:
            lark("drive", "+delete", "--file-token", prev["doc_id"], "--type", "docx",
                 "--yes", "--as", "user")
        except Exception as e:  # noqa: BLE001
            print(f"WARN could not delete old doc: {e}", file=sys.stderr)

    doc_id, doc_url = build_doc_with_figures(title, body_xml, manifest)
    print(f"doc: {doc_url}")

    # Place under the Wiki domain node.
    node = ensure_domain_node(cfg, domain)
    space = cfg["wiki_space_id"]
    try:
        lark("wiki", "+move", "--obj-token", doc_id, "--obj-type", "docx",
             "--target-space-id", space, "--target-parent-token", node, "--as", "user")
        print(f"moved into wiki/{domain}")
    except Exception as e:  # noqa: BLE001
        print(f"WARN wiki move failed: {e}", file=sys.stderr)

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
    cfg["notes"][note_rel] = {"doc_id": doc_id, "url": doc_url,
                              "record_id": rec_id, "hash": h}
    save_cfg(cfg)
    print(json.dumps({"doc": doc_url, "figures": len(manifest),
                      "wiki": f"{domain}", "base_record": rec_id}, ensure_ascii=False))


if __name__ == "__main__":
    main()
