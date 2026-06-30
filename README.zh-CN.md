# Marginalia

<p align="center">
  <em>把论文读透，并发布成一份图文飞书文档，而不是一段松散摘要。</em>
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

**Marginalia**（书页边的批注）是一个**论文精读 skill**。一句话：*把一篇论文读透并发布成飞书文档——git 仓库只装 skill,笔记和知识库都在飞书。*

它融合两个项目的长处——

- 深度阅读的**「大脑」**参考 [FeijiangHan/PaperForge](https://github.com/FeijiangHan/PaperForge)：重建作者思路、最脆弱的假设、最强反例、非增量 follow-up idea、信息来源纪律、写作风格。
- 持久化的**「身体」**参考 [LazyDreamingDog/paper-reading-workflow](https://github.com/LazyDreamingDog/paper-reading-workflow)：统一笔记模板、`毒舌评论`——持久化到**飞书**知识库（Wiki 树 + 可筛选 Base 索引）。

同时支持 **Claude Code** 和 **Codex**，通用领域 + 可插拔领域 profile。

## 它做什么

- 把论文**标题 / DOI / arXiv / OpenReview / 出版社 / GitHub / 本地 PDF** 变成一份结构化中文笔记。
- 强调动机、basic idea、方法推理、证据、最脆弱假设、反例与个人 takeaway。
- TL;DR 之后给一段够狠的 `毒舌评论`——不是中性复述。
- **发布到飞书（Lark）作为正式产物**：每篇笔记发布成带图表、公式、表格的文档，按领域挂进知识库（Wiki）树，并在多维表格（Base）里登记成可筛选索引。本地 md 是 gitignore 的运行期缓存（写作草稿 + grep + 重发），不是版本化的源。

## 它怎么读

不是复述 abstract。skill 内部跑一套有纪律的精读流程（完整版见 [`reading-method.md`](skills/marginalia/references/reading-method.md)）：三遍阅读（主张 → 机制 → 证据）→ 对比最接近的 prior work 校准 novelty → 只用论文之前已有的知识重建作者思路 → 把论文当作要被质疑的对象做批判性综合 → 最后做读数复核,不让任何狠话撑在读错的数字上。

## 仓库结构

```text
marginalia/
├── skills/marginalia/        # 可安装的 skill 本体
│   ├── SKILL.md
│   ├── agents/openai.yaml    # Codex 展示元数据
│   ├── references/           # 按需加载：流程 / 模板 / 风格 / 来源解析 / git / 领域
│   └── scripts/              # publish_to_feishu.py、extract_figures.py
├── .agent                    # Codex 工作流文件
└── examples/                 # 示例笔记（演示资产）
```

> 知识库在**飞书**（Wiki + Base），不在本仓库。本地 md 笔记落在 `notes/`、发布映射在 `.marginalia/feishu.json`——两者都是 gitignore 的运行期缓存，不版本化。

## 安装

### Claude Code

```bash
mkdir -p ~/.claude/skills
cp -R skills/marginalia ~/.claude/skills/marginalia
```

之后在对话里直接发论文链接或标题，skill 会自动触发。

### Codex

发布到 npm 后：

```bash
npx marginalia-codex-skill
# 可选：同时把工作流文件放到你的论文知识库根目录
npx marginalia-codex-skill --agent-dir /path/to/your-paper-repo
```

直接从 GitHub 安装：

```bash
npx --package github:Excelius-Wang/marginalia marginalia-codex-skill
```

手动安装：

```bash
mkdir -p ~/.codex/skills
cp -R skills/marginalia ~/.codex/skills/
# 在论文知识库根目录放一份工作流文件
cp .agent /path/to/your-paper-repo/.agent
```

## 用法

```text
精读这篇论文：https://arxiv.org/abs/1706.03762
读一下 /path/to/paper.pdf，发布到飞书 ml/ 领域
精读 Attention Is All You Need，并发布到飞书
```

## 笔记风格

模板见 [`note-schema.md`](skills/marginalia/references/note-schema.md)。主要段落：元数据、TL;DR、毒舌评论、研究问题、前人工作、论文自述贡献、作者思路重建、核心直觉、方法与流程、核心数学推导 *(可选)*、威胁模型 *(可选)*、实验评估、复现配置 *(可选)*、关键图表、最脆弱的假设、最小复现实验、最强反例、优势 / 局限、我的判断、后续研究设想、相关论文、开放问题。

模板是上限不是清单——按论文类型裁剪，别为填满而堆 `N/A`。完整示例见 [`examples/`](examples/) 目录。

## 发布到飞书（Lark）

把每篇笔记发布成带原生图表、公式、表格的飞书文档，按领域挂进知识库（Wiki）树，并在多维表格（Base）登记可筛选索引。**飞书是正式产物，也是唯一索引**；本地 md 是 gitignore 的运行期缓存。详见 [`feishu-publish.md`](skills/marginalia/references/feishu-publish.md)。

```bash
# 需先 lark-cli auth login（用户身份）；用项目 venv 的 python，PyMuPDF/pdf2image 才解析得到
# （直接用裸 python3 会 ModuleNotFoundError）
.marginalia/venv/bin/python skills/marginalia/scripts/publish_to_feishu.py "notes/<domain>/<note>.md" --pdf /path/to/paper.pdf
```

亮点：

- **语义渲染**——招牌小节渲染成彩色 callout，优势/局限并排成 grid，顶部「导读」callout 给出配色图例 + 招牌小节的速读路径。
- **图表**——用 PyMuPDF 从 PDF 几何抽取；`[hero]` 把概览图做头图，`[@锚点]` 把图穿插到对应讨论处，`[box=...]` 手动框定裁歪的图。
- **fail-loud 校验门禁**——颜色标记嵌套、XML 不平衡、LaTeX 损坏（花括号 / `\left`-`\right` / `\begin`-`\end` 配对）、锚点失配都会**中止发布**，绝不带病上线。
- **幂等且 URL 稳定**——重发原地更新同一篇文档（同一台机器上靠本地映射）；指向库内其他笔记的交叉链接会解析成对方的飞书 URL，而本地 md 保持可移植的相对路径。

幂等映射 `.marginalia/feishu.json` 与派生图 `.marginalia/figs/` 都是 gitignore 的运行期缓存。**飞书多维表格（Base）是可筛选的索引**——仓库里不再维护论文清单。示例笔记见 [`examples/`](examples/) 目录。

## 后续

发现功能（从 arXiv + Hugging Face 抓热门 / 新论文、出每日 digest）将作为独立项目 `paper-radar`，届时复用本仓库的 `source-resolution` / `git-workflow` / `domains`。

## 致谢

感谢 [PaperForge](https://github.com/FeijiangHan/PaperForge) 与 [paper-reading-workflow](https://github.com/LazyDreamingDog/paper-reading-workflow) 两个项目的启发。

## License

[MIT](LICENSE)
