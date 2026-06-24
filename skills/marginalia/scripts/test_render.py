#!/usr/bin/env python3
"""Regression tests for the marginalia note -> DocxXML renderer (publish_to_feishu).

Run with the project venv so PyMuPDF/Pillow imports in publish_to_feishu resolve:
    .marginalia/venv/bin/python skills/marginalia/scripts/test_render.py

Locks in the two render footguns that bit a real publish so they can't regress:
  1. currency `$` desync — a bare `$` paired with a later `$` and swallowed prose.
     Now `$...$` is always math; a literal dollar is `\\$`; an unescaped one that
     swallows CJK prose is flagged loud by lint_latex.
  2. `</li>` imbalance — an ordered sub-list starting indented right after a bullet.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_to_feishu as P  # noqa: E402

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def li_balanced(xml):
    return xml.count("<li>") == len(re.findall(r"</li>", xml))


@case
def escaped_dollar_renders_as_literal_currency():
    out = P.inline(r"成本 \$173/万次、定价 \$0.75/M")
    assert "$173" in out and "$0.75" in out, out
    assert "<latex>" not in out, out


@case
def inline_math_renders_including_digit_leading():
    out = P.inline("缩放 $2^{10}$、复杂度 $O(n^2)$、$3\\times3$ 卷积")
    assert "<latex>2^{10}</latex>" in out, out
    assert "<latex>O(n^2)</latex>" in out, out
    assert "<latex>3\\times3</latex>" in out, out


@case
def unescaped_currency_desync_is_caught_loud():
    # a bare `$` money sign pairs with a later `$` and swallows CJK prose -> must flag
    probs = P.lint_latex("定价 $0.75/M、成本 $173,公式 $x$")
    assert any("中文" in p for p in probs), probs


@case
def escaped_currency_passes_lint():
    probs = P.lint_latex(r"定价 \$0.75/M、成本 \$173,公式 $x+1$")
    assert not probs, probs


@case
def broken_digit_leading_formula_is_caught():
    # the case the discarded `$(?!\d)` fix silently swallowed
    assert P.lint_latex("坏公式 $2^{n$"), "missing brace in a digit-leading formula not caught"


@case
def valid_formulas_pass():
    md = r"损失 $\mathcal{L}=\mathbb{E}\big[-\log p\big]$ 与 $$\sum_{i=1}^{n} x_i$$"
    assert not P.lint_latex(md), P.lint_latex(md)


@case
def nested_ul_stays_balanced():
    xml = P.render_blocks(["- 关键图:", "  - Fig.2 a", "  - Fig.1 b", "- 关键表:x"])
    assert li_balanced(xml), xml


@case
def ordered_sublist_after_bullet_balanced():
    # the `</li>` imbalance: an ordered list starting indented after a bullet flush
    xml = P.render_blocks(["- lead:", "  1. one", "  2. two", "  3. three", "- after"])
    assert li_balanced(xml), xml
    assert not [p for p in P.lint_xml(xml) if "li" in p], P.lint_xml(xml)


@case
def oversized_atomic_block_is_caught():
    # a callout/grid/table renders to ONE atomic block that can't be split; above
    # MAX_CHUNK its lone chunk would blow Feishu's --content cap and truncate on
    # send, so the size gate must fail loud (one ceiling = MAX_CHUNK, not 8000).
    huge = "<callout>" + "x" * (P.MAX_CHUNK + 400) + "</callout>"
    assert any("原子块过长" in p for p in P.lint_xml(huge)), P.lint_xml(huge)


@case
def normal_sized_block_passes_size_gate():
    ok = "<callout>" + "x" * 400 + "</callout>"
    assert not [p for p in P.lint_xml(ok) if "原子块" in p], P.lint_xml(ok)


@case
def caption_keeps_literal_currency():
    # `\$` is a literal dollar -> caption shows `$173`, not a stray backslash
    assert P._clean_caption(r"成本 \$173/万次") == "成本 $173/万次", P._clean_caption(r"成本 \$173/万次")


@case
def caption_drops_formula_delimiters():
    assert "$" not in P._clean_caption("复杂度 $O(n)$ 对比"), P._clean_caption("复杂度 $O(n)$ 对比")


def main():
    failed = 0
    for fn in CASES:
        try:
            fn()
            print(f"ok   {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
