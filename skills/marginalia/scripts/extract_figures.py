#!/usr/bin/env python3
"""Extract paper figures/tables from a PDF as cropped PNGs.

Given a source PDF and a list of `LABEL@PAGE` specs (e.g. "Figure 6@9"),
locate each artifact's caption via `pdftotext -bbox`, then crop the page
image (rendered with pdf2image) to the artifact region using a row-ink-density
gap heuristic, trimming surrounding whitespace.

This module is deliberately Lark-independent and deterministic — it is the
"figure source" half of the Feishu publishing pipeline. Placement/upload is
handled separately (see references/feishu-publish.md).

Requires: poppler (pdftotext), pdf2image, Pillow. No PyMuPDF needed.

Usage:
    python3 extract_figures.py --pdf paper.pdf --out figs/ \
        "Figure 1@1" "Figure 6@9" "Figure 7@11"

Prints a JSON manifest [{label, page, path, width, height}] to stdout.
"""
import argparse
import json
import re
import subprocess
import sys
from html import unescape
from pathlib import Path

from pdf2image import convert_from_path
from PIL import Image, ImageChops, ImageDraw

WORD_RE = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>'
)
PAGE_RE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">')


def page_words(pdf, page):
    """Return (page_w_pt, page_h_pt, [(xMin,yMin,xMax,yMax,text), ...]) for a page."""
    out = subprocess.run(
        ["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf, "-"],
        capture_output=True, text=True, check=True,
    ).stdout
    pm = PAGE_RE.search(out)
    pw, ph = (float(pm.group(1)), float(pm.group(2))) if pm else (612.0, 792.0)
    words = [(float(a), float(b), float(c), float(d), unescape(t))
             for a, b, c, d, t in WORD_RE.findall(out)]
    return pw, ph, words


def find_caption_band(words, label):
    """Find the (yMin, yMax) of the caption line for `label` (e.g. 'Figure 6').

    Matches the kind word ('Figure'/'Table'/'Fig.') immediately followed by the
    number, then returns the vertical band of that whole text line.
    """
    kind, num = label.split()
    kind_l, num_l = kind.lower().rstrip("."), num.lower()
    cands = []
    for i, (x0, y0, x1, y1, t) in enumerate(words):
        tl = t.lower().rstrip(".:")
        if tl in (kind_l, "fig") and i + 1 < len(words):
            if words[i + 1][4].lower().rstrip(".:") != num_l:
                continue
            # A caption starts the line ("Figure 2: ..."); an in-text reference
            # ("depicted in Figure 2") has words to its left on the same line.
            line_lead = not any(w[2] <= x0 and not (w[3] < y0 - 2 or w[1] > y1 + 2)
                                for w in words)
            cands.append((line_lead, i, x0, y0, y1))
    if not cands:
        return None
    cands.sort(key=lambda c: (not c[0], c[3]))   # prefer line-leading, then topmost
    _, i, x0, y0, y1 = cands[0]
    ys = [(w[1], w[3]) for w in words if not (w[3] < y0 - 2 or w[1] > y1 + 2)]
    return min(a for a, _ in ys), max(b for _, b in ys), (x0 + words[i + 1][2]) / 2.0


def horizontal_segment(region, xc_px, dpi, thresh=4):
    """Trim a crop to the content column containing x-center `xc_px`.

    Handles 2-column / side-by-side-with-text layouts: detect vertical
    whitespace gutters splitting the band into column segments, then keep the
    segment under the caption. Single-column figures pass through unchanged.
    """
    g = region.convert("L")
    W2, _ = g.size
    rowimg = g.resize((W2, 1), Image.BOX)
    dark = [255 - m for m in rowimg.getdata()]
    gap_need = int(0.16 * dpi)
    segs, start, run = [], None, 0
    for x in range(W2):
        if dark[x] > thresh:
            if start is None:
                start = x
            run = 0
        elif start is not None:
            run += 1
            if run >= gap_need:
                segs.append((start, x - run + 1))
                start, run = None, 0
    if start is not None:
        segs.append((start, W2))
    if len(segs) <= 1:
        return region
    # Only trim when the caption x-center sits INSIDE one ink column (true
    # 2-column / figure-beside-text layout). A centered figure with a
    # left-margin caption has its x-center in a gutter -> keep the whole band,
    # otherwise we'd clip the figure to one sub-panel (or to empty margin).
    pick = next((s for s in segs if s[0] <= xc_px <= s[1]), None)
    if pick is None or (pick[1] - pick[0]) < 0.35 * W2:
        # No column under the caption, or the "column" is just a figure sub-panel
        # (a real text column is ~half the page) -> keep the full band.
        return region
    return region.crop((pick[0], 0, pick[1], region.size[1]))


def row_darkness(gray):
    """Per-row darkness (0=white .. 255=black) for an 'L'-mode image, pure Pillow.

    Resizing the width to 1 with a BOX filter averages each row to one pixel.
    """
    H = gray.size[1]
    col = gray.resize((1, H), Image.BOX)
    return [255 - m for m in col.getdata()]


def text_lines(words):
    """Group words into text lines by vertical-center proximity (within ~0.6 line
    height), so adjacent lines don't chain into one giant band. Each line carries
    its y-band and horizontal coverage (summed word width)."""
    lines = []
    for x0, y0, x1, y1, _ in sorted(words, key=lambda w: (w[1] + w[3]) / 2):
        yc, h = (y0 + y1) / 2, y1 - y0
        if lines and yc - lines[-1]["yc"] <= max(3.0, 0.6 * h):
            ln = lines[-1]
            ln["y0"], ln["y1"] = min(ln["y0"], y0), max(ln["y1"], y1)
            ln["yc"], ln["cov"] = yc, ln["cov"] + (x1 - x0)
        else:
            lines.append({"yc": yc, "y0": y0, "y1": y1, "cov": x1 - x0})
    return lines


def body_text_bottom_pt(words, pw, cap_top_pt):
    """yMax (pt) of the lowest full-width prose line above the caption — figures
    must not extend above it (keeps page titles/logos/other-figures out)."""
    above = [w for w in words if w[3] <= cap_top_pt - 1]
    fulls = [ln["y1"] for ln in text_lines(above) if ln["cov"] >= 0.6 * pw]
    return max(fulls) if fulls else 0.0


# ------------------------------------------------------------ PyMuPDF backend
# General, geometry-based extraction: read the PDF's own text/drawing/image
# block coordinates (vector + raster handled uniformly) instead of guessing from
# rendered pixels. This is the primary path; the poppler heuristic below is a
# fallback for environments without PyMuPDF.

def _caption_rect(page, kind, num):
    """Rect of the caption *line* starting with e.g. 'Figure 6' / 'Table 1'."""
    import fitz
    starts = (f"{kind} {num}", f"figure {num}", f"fig. {num}", f"fig {num}")
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            txt = "".join(s["text"] for s in ln["spans"]).strip().lower()
            if any(txt.startswith(s) for s in starts):
                return fitz.Rect(ln["bbox"])
    return None


def _crop_fitz(pdf, page, label, out_dir, dpi, box):
    import fitz
    kind, num = label.split()
    kind = "table" if kind.lower().startswith("tab") else "figure"
    doc = fitz.open(pdf)
    pg = doc[page - 1]
    H = pg.rect.height
    if box is not None:
        rect = fitz.Rect(*box)
    else:
        cap = _caption_rect(pg, kind, num)
        if cap is None:
            return None
        # figure = union of vector drawings + image blocks sitting above the
        # caption (within ~0.9 page), then clamp the top to the lowest text
        # block above the cluster (keeps titles/other figures/prose out).
        gfx = [fitz.Rect(p["rect"]) for p in pg.get_drawings()]
        gfx += [fitz.Rect(b["bbox"]) for b in pg.get_text("dict")["blocks"]
                if b.get("type") == 1]
        above = [r for r in gfx if r.y1 <= cap.y0 + 1 and r.y0 >= cap.y0 - 0.9 * H
                 and r.width > 5 and r.height > 5]
        if not above:
            return None
        rect = above[0]
        for r in above[1:]:
            rect |= r
        tb = [fitz.Rect(b["bbox"]) for b in pg.get_text("dict")["blocks"]
              if b.get("type") == 0 and fitz.Rect(b["bbox"]).y1 <= rect.y0 + 2]
        if tb:
            rect.y0 = max(rect.y0, max(t.y1 for t in tb))
        rect |= cap                       # include the caption line
        rect &= pg.rect                   # keep inside the page
    z = dpi / 72.0
    pix = pg.get_pixmap(clip=rect, matrix=fitz.Matrix(z, z))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = label.lower().replace(" ", "").replace(".", "")
    path = out_dir / f"{slug}_p{page}.png"
    pix.save(path)
    return {"label": label, "page": page, "path": str(path),
            "width": pix.width, "height": pix.height}


def crop_artifact(pdf, page, label, out_dir, dpi=200, box=None):
    """Extract one figure/table. Prefer the geometric PyMuPDF backend; fall back
    to the poppler+Pillow heuristic if PyMuPDF isn't available or finds nothing."""
    try:
        import fitz  # noqa: F401
        res = _crop_fitz(pdf, page, label, out_dir, dpi, box)
        if res is not None:
            return res
    except ImportError:
        pass
    return _crop_poppler(pdf, page, label, out_dir, dpi, box)


def _crop_poppler(pdf, page, label, out_dir, dpi=200, box=None):
    pw, ph, words = page_words(pdf, page)
    band = find_caption_band(words, label)
    img = convert_from_path(pdf, dpi=dpi, first_page=page, last_page=page)[0].convert("RGB")
    W, H = img.size
    scale = dpi / 72.0

    if box is not None:
        # Manual override (PDF points) for figures the heuristics can't isolate
        # (e.g. side-by-side figure+text). Crop exactly, then whitespace-trim.
        bx0, by0, bx1, by1 = box
        crop = img.crop((max(0, int(bx0 * scale)), max(0, int(by0 * scale)),
                         min(W, int(bx1 * scale)), min(H, int(by1 * scale))))
    elif band is None:
        crop = img
    else:
        cap_bot_px = int(band[1] * scale)
        # A figure is the GRAPHICS (lines, arrows, colored boxes) above its
        # caption. White out every text word — body text AND in-figure labels —
        # so only graphics remain, then take that ink's bbox. This isolates the
        # figure's true extent for centered, tall, AND side-by-side layouts
        # (where text shares the figure's rows) without column heuristics.
        gfx = img.convert("L")
        d = ImageDraw.Draw(gfx)
        for x0, y0, x1, y1, _ in words:
            d.rectangle([x0 * scale - 1, y0 * scale - 1, x1 * scale + 1, y1 * scale + 1],
                        fill=255)
        cap_top_px = int(band[0] * scale)
        win_top = max(0, cap_top_px - int(0.85 * H))   # search window above the caption
        window = gfx.crop((0, win_top, W, max(win_top + 1, cap_top_px - 2)))
        gbox = ImageChops.difference(window, Image.new("L", window.size, 255)).getbbox()
        if gbox:
            gx0, gy0, gx1, gy1 = gbox
            # Clamp the top so the figure never reaches above the last full-width
            # prose line (excludes page titles/logos/other figures the bbox grabs).
            fy0 = max(win_top + gy0, int(body_text_bottom_pt(words, pw, band[0]) * scale) + 4)
            # keep the caption fully visible: union x with the caption line's words
            cap_x = [(w[0] * scale, w[2] * scale) for w in words
                     if not (w[3] < band[0] - 2 or w[1] > band[1] + 2)]
            x0 = min([gx0] + [c[0] for c in cap_x])
            x1 = max([gx1] + [c[1] for c in cap_x])
            crop = img.crop((max(0, int(x0) - 8), max(0, fy0 - 8),
                             min(W, int(x1) + 8), min(H, cap_bot_px + 4)))
        else:   # no graphics found: fall back to a band above the caption
            crop = img.crop((0, max(0, cap_top_px - int(0.4 * H)), W, min(H, cap_bot_px + 4)))

    # Final tight trim of uniform (white) margins on all sides.
    g = crop.convert("L")
    bbox = ImageChops.difference(g, Image.new("L", g.size, 255)).getbbox()
    if bbox:
        pad = 6
        x0, y0, x1, y1 = bbox
        crop = crop.crop((max(0, x0 - pad), max(0, y0 - pad),
                          min(crop.size[0], x1 + pad), min(crop.size[1], y1 + pad)))

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = label.lower().replace(" ", "").replace(".", "")
    path = out_dir / f"{slug}_p{page}.png"
    crop.save(path)
    return {"label": label, "page": page, "path": str(path),
            "width": crop.size[0], "height": crop.size[1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("specs", nargs="+", help='"Figure 6@9" "Table 1@2" ...')
    args = ap.parse_args()

    manifest = []
    for spec in args.specs:
        label, page = spec.rsplit("@", 1)
        try:
            manifest.append(crop_artifact(args.pdf, int(page), label.strip(), args.out, args.dpi))
        except Exception as e:  # noqa: BLE001 - report and continue
            print(f"WARN failed {spec}: {e}", file=sys.stderr)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
