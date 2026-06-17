# Marginalia

<p align="center">
  <em>把一篇论文变成一份可长期复用的深度笔记，而不是一段松散摘要。</em>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/Claude%20Code-supported-7c3aed" alt="Claude Code">
  <img src="https://img.shields.io/badge/Codex-supported-10a37f" alt="Codex">
  <img src="https://img.shields.io/badge/notes-Chinese-orange" alt="Notes in Chinese">
</p>

<p align="center">
  <a href="README.md">English</a> · <b>简体中文</b>
</p>

---

**Marginalia**（书页边的批注）是一个**论文精读 skill**：深度主动阅读 + 持久化知识库。它融合两个项目的长处——

- 深度阅读的**「大脑」**参考 [FeijiangHan/PaperForge](https://github.com/FeijiangHan/PaperForge)：重建作者思路、最脆弱的假设、最强反例、非增量 follow-up idea、信息来源纪律、写作风格。
- 持久化的**「身体」**参考 [LazyDreamingDog/paper-reading-workflow](https://github.com/LazyDreamingDog/paper-reading-workflow)：统一笔记模板、`毒舌评论`、git 知识库、README 索引。

同时支持 **Claude Code** 和 **Codex**，通用领域 + 可插拔领域 profile。

## 它做什么

- 把论文**标题 / DOI / arXiv / OpenReview / 出版社 / GitHub / 本地 PDF** 变成一份结构化中文笔记。
- 强调动机、basic idea、方法推理、证据、最脆弱假设、反例与个人 takeaway。
- TL;DR 之后给一段够狠的 `毒舌评论`——不是中性复述。
- 笔记落到 `notes/`，回填 README 索引，并 commit/push。
- 可选**发布到飞书（Lark）**：每篇笔记发布成带图表、公式、表格的文档，按领域挂进知识库（Wiki）树，并在多维表格（Base）里登记成可筛选索引。

## 它怎么读

不是复述 abstract。skill 内部跑一套有纪律的精读流程（见 [`reading-method.md`](skills/marginalia/references/reading-method.md)）：

1. **解析来源**并通读全文。
2. **三遍阅读**——问题与主张 → 方法与机制 → 证据。
3. **校准 novelty**：对比 2–3 篇最接近的 prior work。
4. **重建作者思路**：只用这篇论文之前已存在的知识。
5. **批判性综合**：把论文当成需要被质疑的对象。
6. **读数复核**：每个引用的图/表数字都回原文核对，绝不让读错的数字撑起一句狠话。

## 仓库结构

```text
marginalia/
├── skills/marginalia/        # 可安装的 skill 本体
│   ├── SKILL.md
│   ├── agents/openai.yaml    # Codex 展示元数据
│   ├── references/           # 按需加载：流程 / 模板 / 风格 / 来源解析 / git / 领域
│   └── scripts/              # publish_to_feishu.py、extract_figures.py
├── .agent                    # Codex 工作流文件
├── notes/                    # 你的论文笔记（知识库）
└── examples/                 # 示例笔记
```

## 安装

### Claude Code

```bash
mkdir -p ~/.claude/skills
cp -R skills/marginalia ~/.claude/skills/marginalia
```

之后在对话里直接发论文链接或标题，skill 会自动触发。

### Codex

```bash
mkdir -p ~/.codex/skills
cp -R skills/marginalia ~/.codex/skills/
# 在论文知识库根目录放一份工作流文件
cp .agent /path/to/your-paper-repo/.agent
```

## 用法

```text
精读这篇论文：https://arxiv.org/abs/1706.03762
读一下 /path/to/paper.pdf，整理到 notes/ml/
精读 Attention Is All You Need，并按索引规范回填
```

## 笔记风格

模板见 [`note-schema.md`](skills/marginalia/references/note-schema.md)。主要段落：元数据、TL;DR、毒舌评论、研究问题、前人工作、论文自述贡献、作者思路重建、核心直觉、方法与流程、核心数学推导 *(可选)*、威胁模型 *(可选)*、实验评估、复现配置 *(可选)*、关键图表、最脆弱的假设、最小复现实验、最强反例、优势 / 局限、我的判断、后续研究设想、相关论文、开放问题。

模板是上限不是清单——按论文类型裁剪，别为填满而堆 `N/A`。完整示例见 [`examples/`](examples/) 目录。

## 发布到飞书（Lark）

把每篇笔记发布成带原生图表、公式、表格的飞书文档，按领域挂进知识库（Wiki）树，并在多维表格（Base）登记可筛选索引。本地 md 仍是**版本化的源**，飞书是**渲染产物**。详见 [`feishu-publish.md`](skills/marginalia/references/feishu-publish.md)。

```bash
# 需先 lark-cli auth login（用户身份）
python3 skills/marginalia/scripts/publish_to_feishu.py "notes/<domain>/<note>.md" --pdf /path/to/paper.pdf
```

亮点：

- **语义渲染**——招牌小节渲染成彩色 callout，优势/局限并排成 grid，顶部「导读」callout 给出配色图例 + 招牌小节的速读路径。
- **图表**——用 PyMuPDF 从 PDF 几何抽取；`[hero]` 把概览图做头图，`[@锚点]` 把图穿插到对应讨论处，`[box=...]` 手动框定裁歪的图。
- **fail-loud 校验门禁**——颜色标记嵌套、XML 不平衡、LaTeX 损坏（花括号 / `\left`-`\right` / `\begin`-`\end` 配对）、锚点失配都会**中止发布**，绝不带病上线。
- **幂等且 URL 稳定**——重发原地更新同一篇文档；指向库内其他笔记的交叉链接会解析成对方的飞书 URL，而本地 md 保持可移植的相对路径。

幂等映射记于 `.marginalia/feishu.json`；派生图在 `.marginalia/figs/`（已 gitignore）。

## 论文索引

> 飞书多维表格是可筛选的主索引；下表为离线备查。新增笔记时登记，`TODO`→`DONE` 在笔记文件存在后再改。

| Venue / Year | Title | 领域 | 笔记 | Status |
| --- | --- | --- | --- | --- |
| NeurIPS 2017 | Attention Is All You Need（示例模板） | ml | `examples/【NeurIPS‘2017】attention-is-all-you-need.md` | DONE (example) |

## 后续

发现功能（从 arXiv + Hugging Face 抓热门 / 新论文、出每日 digest）将作为独立项目 `paper-radar`，届时复用本仓库的 `source-resolution` / `git-workflow` / `domains`。

## 致谢

感谢 [PaperForge](https://github.com/FeijiangHan/PaperForge) 与 [paper-reading-workflow](https://github.com/LazyDreamingDog/paper-reading-workflow) 两个项目的启发。

## License

[MIT](LICENSE)
