# Marginalia

> 把一篇论文变成一份可长期复用的中文深度笔记，而不是一段松散摘要。

Marginalia（书页边的批注）是一个**论文精读 skill**：深度主动阅读 + 持久化知识库。它融合两个项目的长处——

- 深度阅读的"大脑"参考 [FeijiangHan/PaperForge](https://github.com/FeijiangHan/PaperForge)：重建作者思路、最脆弱的假设、最强反例、非增量 follow-up idea、信息来源纪律、写作风格。
- 持久化的"身体"参考 [LazyDreamingDog/paper-reading-workflow](https://github.com/LazyDreamingDog/paper-reading-workflow)：统一笔记模板、`毒舌评论`、git 知识库、README 索引。

同时支持 **Claude Code** 和 **Codex**，通用领域 + 可插拔领域 profile。

## 它做什么

- 把论文标题 / DOI / arXiv / OpenReview / 出版社 / GitHub / 本地 PDF 变成一份结构化中文笔记。
- 强调动机、basic idea、方法推理、证据、最脆弱假设、反例与个人 takeaway。
- TL;DR 之后给一段够狠的 `毒舌评论`。
- 笔记落到 `notes/`，回填 README 索引，并 commit/push。

## 仓库结构

```text
marginalia/
├── skills/marginalia/        # 可安装的 skill 本体
│   ├── SKILL.md
│   ├── agents/openai.yaml    # Codex 展示元数据
│   └── references/           # 按需加载：流程 / 模板 / 风格 / 来源解析 / git / 领域
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

模板见 [skills/marginalia/references/note-schema.md](skills/marginalia/references/note-schema.md)。主要段落：Metadata、TL;DR、毒舌评论、研究问题、前人工作、作者思路重建、核心 Intuition、Method、Evaluation、Key Artifacts、最脆弱的假设、最小复现实验、最强反例、Strengths / Limitations、My Takeaways、Follow-up Idea、Related Papers、Open Questions。

完整示例见 `examples/` 目录。

## 论文索引

> 新增笔记时在这里登记；`TODO`→`DONE` 在笔记文件存在后再改。

| Venue / Year | Title | 领域 | 笔记 | Status |
| --- | --- | --- | --- | --- |
| NeurIPS 2017 | Attention Is All You Need | ml | `examples/【NeurIPS‘2017】attention-is-all-you-need.md` | DONE (example) |
| arXiv 2026 | Lance: Unified Multimodal Modeling by Multi-Task Synergy | ml | `notes/ml/【arXiv‘2026】lance-unified-multimodal.md` | DONE |

## 后续

发现功能（从 arXiv + HuggingFace 抓热门 / 新论文、出每日 digest）将作为独立项目 `paper-radar`，届时复用本仓库的 `source-resolution` / `git-workflow` / `domains`。

## 致谢

感谢 [PaperForge](https://github.com/FeijiangHan/PaperForge) 与 [paper-reading-workflow](https://github.com/LazyDreamingDog/paper-reading-workflow) 两个项目的启发。

## License

MIT
