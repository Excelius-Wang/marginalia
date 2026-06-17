# Marginalia

<p align="center">
  <em>Read a paper deeply — and publish it as a rich Feishu document, not a loose summary.</em>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/Claude%20Code-supported-7c3aed" alt="Claude Code">
  <img src="https://img.shields.io/badge/Codex-supported-10a37f" alt="Codex">
  <img src="https://img.shields.io/badge/notes-Chinese-orange" alt="Notes in Chinese">
</p>

<p align="center">
  <b>English</b> · <a href="README.zh-CN.md">简体中文</a>
</p>

---

**Marginalia** (the notes scribbled in a book's margins) is a **deep paper-reading skill**. In one line: *it reads a paper deeply and publishes it as a Feishu document — the git repo holds only the skill; the notes and the knowledge base live in Feishu.*

It fuses the strengths of two projects —

- The **"brain"** of deep reading, after [FeijiangHan/PaperForge](https://github.com/FeijiangHan/PaperForge): reconstruct the author's reasoning, surface the most fragile assumption, design the strongest counterexample, propose non-incremental follow-up ideas, keep source discipline, and write with style.
- The **"body"** of persistence, after [LazyDreamingDog/paper-reading-workflow](https://github.com/LazyDreamingDog/paper-reading-workflow): a unified note template and a `Sharp Verdict` — persisted to a **Feishu** knowledge base (Wiki tree + filterable Base index).

It runs on both **Claude Code** and **Codex**, with a general domain plus pluggable per-domain profiles.

## What it does

- Turns a paper **title / DOI / arXiv / OpenReview / publisher / GitHub / local PDF** into one structured note.
- Emphasizes motivation, the basic idea, the reasoning behind the method, the evidence, the most fragile assumption, counterexamples, and your own takeaways.
- Follows the TL;DR with a genuinely sharp `Sharp Verdict` — not a neutral recap.
- **Publishes each note to Feishu (Lark)** as the system of record — a rich document with figures, formulas, and tables, filed into a Wiki tree by domain and registered in a filterable Base index. The local markdown is a gitignored runtime cache (drafting buffer + grep + re-publish), not a versioned source.

## How it reads

Not a paraphrase of the abstract. The skill runs a disciplined internal method (full version in [`reading-method.md`](skills/marginalia/references/reading-method.md)): three passes (claims → mechanism → evidence) → calibrate novelty against the nearest prior work → reconstruct the author's idea from only what was known *before* the paper → critical synthesis that treats the paper as something to be challenged → a final number re-check so no sharp claim leans on a misread figure.

## Repository layout

```text
marginalia/
├── skills/marginalia/        # the installable skill itself
│   ├── SKILL.md
│   ├── agents/openai.yaml    # Codex display metadata
│   ├── references/           # progressive disclosure: method / schema / style / source / git / domains
│   └── scripts/              # publish_to_feishu.py, extract_figures.py
├── .agent                    # Codex workflow file
└── examples/                 # example notes (demo asset)
```

> The knowledge base lives in **Feishu** (Wiki + Base), not in this repo. Local notes land under `notes/` and the publish mapping under `.marginalia/feishu.json` — both gitignored runtime caches, not versioned.

## Install

### Claude Code

```bash
mkdir -p ~/.claude/skills
cp -R skills/marginalia ~/.claude/skills/marginalia
```

Then just drop a paper link or title into the conversation — the skill triggers automatically.

### Codex

```bash
mkdir -p ~/.codex/skills
cp -R skills/marginalia ~/.codex/skills/
# place a workflow file at the root of your paper knowledge base
cp .agent /path/to/your-paper-repo/.agent
```

## Usage

```text
Deep-read this paper: https://arxiv.org/abs/1706.03762
Read /path/to/paper.pdf and publish it to Feishu under ml/
Deep-read "Attention Is All You Need" and publish it
```

## Note style

See the template in [`note-schema.md`](skills/marginalia/references/note-schema.md). Core sections: Metadata, TL;DR, Sharp Verdict, Research Question, Prior Work, Claimed Contributions, Reconstructing the Idea, Core Intuition, Method & Pipeline, Math Derivation *(optional)*, Threat Model *(optional)*, Evaluation, Repro Config *(optional)*, Key Artifacts, Most Fragile Assumption, Minimal Reproduction, Strongest Counterexample, Strengths / Limitations, My Takeaways, Follow-up Idea, Related Papers, Open Questions.

The template is a ceiling, not a checklist — trim sections that don't fit the paper type instead of padding with `N/A`. Full examples live in [`examples/`](examples/).

## Publish to Feishu (Lark)

Each note is published as a Feishu document with native figures, formulas, and tables, filed into a Wiki tree (by domain) and registered in a filterable Base table. **Feishu is the system of record and the only index**; the local markdown is a gitignored runtime cache. Details in [`feishu-publish.md`](skills/marginalia/references/feishu-publish.md).

```bash
# requires `lark-cli auth login` (user identity) first
python3 skills/marginalia/scripts/publish_to_feishu.py "notes/<domain>/<note>.md" --pdf /path/to/paper.pdf
```

Highlights:

- **Semantic rendering** — signature sections become colored callouts; Strengths/Limitations a side-by-side grid; a top "reading guide" callout carries a color legend and a fast-path through the signature sections.
- **Figures** — extracted geometrically from the PDF via PyMuPDF; `[hero]` banners the overview figure, `[@anchor]` inlines a figure next to its discussion, `[box=...]` overrides a bad crop manually.
- **Fail-loud lint gates** — malformed color tags, unbalanced XML, broken LaTeX (brace / `\left`-`\right` / `\begin`-`\end` balance), and bad anchors **abort the publish** instead of shipping broken.
- **Idempotent & stable URLs** — re-publishing updates the same doc in place (on the same machine, via the local mapping); cross-links to other notes resolve to their Feishu URLs while the markdown keeps portable relative paths.

The idempotency mapping (`.marginalia/feishu.json`) and derived figures (`.marginalia/figs/`) are gitignored runtime caches. The **Feishu Base table is the filterable index** — there is no in-repo paper list. An example note lives in [`examples/`](examples/).

## Roadmap

Discovery (pulling trending / new papers from arXiv + Hugging Face and emitting a daily digest) will ship as a separate project, `paper-radar`, reusing this repo's `source-resolution` / `git-workflow` / `domains`.

## Acknowledgements

Thanks to [PaperForge](https://github.com/FeijiangHan/PaperForge) and [paper-reading-workflow](https://github.com/LazyDreamingDog/paper-reading-workflow) for the inspiration.

## License

[MIT](LICENSE)
