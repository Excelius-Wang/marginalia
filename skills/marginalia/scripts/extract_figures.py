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
from PIL import Image

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
    for i, (x0, y0, x1, y1, t) in enumerate(words):
        tl = t.lower().rstrip(".:")
        if tl in (kind_l, "fig") and i + 1 < len(words):
            nxt = words[i + 1][4].lower().rstrip(".:")
            if nxt == num_l:
                # collect words roughly on the same line (y overlap) as the label
                ys = [(w[1], w[3]) for w in words if not (w[3] < y0 - 2 or w[1] > y1 + 2)]
                ymin = min(a for a, _ in ys)
                ymax = max(b for _, b in ys)
                xc = (x0 + words[i + 1][2]) / 2.0   # caption x-center (label words)
                return ymin, ymax, xc
    return None


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
    pick = next((s for s in segs if s[0] <= xc_px <= s[1]),
                max(segs, key=lambda s: s[1] - s[0]))
    return region.crop((pick[0], 0, pick[1], region.size[1]))


def row_darkness(gray):
    """Per-row darkness (0=white .. 255=black) for an 'L'-mode image, pure Pillow.

    Resizing the width to 1 with a BOX filter averages each row to one pixel.
    """
    H = gray.size[1]
    col = gray.resize((1, H), Image.BOX)
    return [255 - m for m in col.getdata()]


def crop_artifact(pdf, page, label, out_dir, dpi=200):
    pw, ph, words = page_words(pdf, page)
    band = find_caption_band(words, label)
    img = convert_from_path(pdf, dpi=dpi, first_page=page, last_page=page)[0].convert("RGB")
    W, H = img.size
    scale = dpi / 72.0

    if band is None:
        # Fallback: whole page, whitespace-trimmed.
        crop = img
    else:
        cap_top_px = int(band[0] * scale)
        cap_bot_px = int(band[1] * scale)
        cap_xc_px = band[2] * scale
        gray = img.convert("L")
        dark = row_darkness(gray)                 # 0=white .. 255=black per row
        thresh = 4                                # a row "has content" above this darkness
        gap_need = int(0.16 * dpi)                # ~0.16in of whitespace = a real gap
        top_margin = int(0.06 * H)

        # Captions sit BELOW the artifact, so first skip the whitespace gap
        # between the caption and the figure bottom, landing on figure content.
        r = cap_top_px - 2
        while r > top_margin and dark[r] <= thresh:
            r -= 1
        # Now scan up THROUGH the figure until the next sustained whitespace gap,
        # which separates the figure from body text (or the page top) above it.
        run = 0
        fig_top = top_margin
        while r > top_margin:
            if dark[r] <= thresh:
                run += 1
                if run >= gap_need:
                    fig_top = r + run
                    break
            else:
                run = 0
            r -= 1
        crop = img.crop((0, fig_top, W, min(H, cap_bot_px + 4)))
        crop = horizontal_segment(crop, cap_xc_px, dpi)

    # Trim uniform (white) margins on all sides.
    g = crop.convert("L")
    from PIL import ImageOps, ImageChops
    bg = Image.new("L", g.size, 255)
    diff = ImageChops.difference(g, bg)
    bbox = diff.getbbox()
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
