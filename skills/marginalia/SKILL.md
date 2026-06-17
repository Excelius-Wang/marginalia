---
name: marginalia
description: 深度精读学术论文，产出结构化的中文研究笔记，带批判性分析——重建作者思路、机制层面讲清方法、找出最脆弱的假设、设计反例、提出非增量的 follow-up 研究方向，并发布成带图表/公式的飞书文档（飞书 Wiki 知识库 + 多维表格索引为正式产物；本地 md 仅运行期缓存，不进 git）。当用户给出论文标题、DOI、arXiv/OpenReview/出版社/GitHub/PDF 链接或本地 PDF，或要求 精读/阅读/总结/分析/批判/复现/归纳贡献/比较相关工作/设计反例/提出后续研究/发布到飞书/同步到飞书，或要 read / summarize / critique / deep-read a paper、design a minimal reproduction or counterexample、propose follow-up research、publish to Feishu 时使用。适用于 ML、NLP、CV、systems、安全、区块链、生物、经济等领域。
---

# Marginalia 论文精读

## 概览（Overview）

用这个 skill 把一篇论文**读透并发布成一份图文飞书文档**，而不是一段松散摘要。一句话定位：**仓库只装 skill;笔记是本地运行期缓存;知识库与索引都在飞书。** 三个优先级：事实落地、显式标注不确定性、和已读论文建立连接。

精读不是复述 abstract。真正的贡献和真正的问题往往藏在 method、实验细节、图表、limitations 和 appendix 里。

这个 skill 把"深度主动阅读"和"持久化知识库"合在一起：

- **主动阅读**——重建作者思路、讲清核心 intuition、找出最脆弱的假设、设计反例、提出后续研究。
- **持久化**——按统一模板写成 markdown，发布成飞书文档，挂进**飞书知识库**（Wiki 按领域建树）并登记**飞书多维表格**（Base 可筛选索引）。**飞书是正式产物与唯一索引**；本地 md 与 `.marginalia/feishu.json` 只是 gitignore 的运行期缓存（支撑重发/原地更新与本地 grep），不进 git。

按需阅读以下 reference（渐进式披露，不要一次全读）：

- 解析论文来源 → `references/source-resolution.md`
- 阅读与分析流程 → `references/reading-method.md`
- 写笔记的输出模板 → `references/note-schema.md`
- 写作风格与信息来源纪律 → `references/style-guide.md`
- 领域标签与子领域分类法 → `references/domains/<领域>.md`
- 产物边界与 git 提交规范 → `references/git-workflow.md`
- 发布到飞书（Wiki 文档 + 多维表格索引）→ `references/feishu-publish.md`

## 工作流（Workflow）

1. **解析来源。** 按 `references/source-resolution.md` 把标题/DOI/arXiv/OpenReview/PDF/GitHub/本地 PDF 解析成可读全文。先查飞书 Base 索引（与本地 `notes/` 缓存）有无同一篇，避免重复建文档；有就走原地更新。记录来源 URL 与访问路径。元数据不确定就标 `Unknown`/`TBD`，绝不编造 venue、年份、code、dataset 或 claim。

2. **判定领域，加载 profile。** 根据论文内容（或用户指定）判断领域，读对应的 `references/domains/<领域>.md` 拿到 `Scope/子领域` 分类法和标签词表；判断不了就用 `general.md`。

3. **深度阅读与分析。** 按 `references/reading-method.md` 执行：三遍阅读 → 校准 novelty → 重建作者思路 → 批判性综合 → **读数复核**（写完后逐一核对笔记里引用的每个关键数字确实对得上原文那一格，别让读错的数字撑起狠话）。全程按 `references/style-guide.md` 的四类信息来源纪律标注（论文声称 / 已有文献 / 合理推断 / 不确定猜测）。

4. **写中文笔记。** 用 `references/note-schema.md` 的模板。重点写好招牌段落：`毒舌评论`、`作者思路重建`、`最脆弱的假设`、`最小复现实验`、`最强反例设计`、`Follow-up Research Idea`；把论文实际超参/数据/算力沉到 `复现配置`。分清"作者展示的"和"你推出的"。按论文类型裁剪模板，整节只能凑出 `N/A` 就整段省略，不要注水。在 `Key Artifacts` 里给关键图/表打 `[p.N]` 页码标记（供发布时抽图），给最能概览全文的那张图加 `[hero]`；**凡承载核心 claim 的图都用 `[@锚文本]` 穿插进正文对应处，别只嵌 hero 一张把其余甩给"见原文"**；关键公式用 `$...$` 内联以便渲染；`相关论文`里若库中已有该笔记就用相对路径交叉链接。**写的同时就做排版判断**：按 `references/style-guide.md` 的语义纪律给核心论断加粗 `**…**`、给专名/机制/指标/优势/风险打彩色标记 `{{b|p|o|g|r:词}}`（不同颜色不同作用），这是写作的一部分，不要留到发布再补。

5. **落盘到本地工作区。** 笔记写到 `notes/<领域>/【VENUE‘YEAR】short-title.md`。这是 gitignore 的运行期缓存（供发布、重发、本地 grep），**不进 git、不回填 README**——索引由飞书 Base 承担。

6. **发布到飞书（正式产物）。** 按 `references/feishu-publish.md` 跑 `.marginalia/venv/bin/python skills/marginalia/scripts/publish_to_feishu.py "<note>" --pdf <pdf>`（用项目 venv 的 python 才能用上 PyMuPDF 几何抽图后端）：生成带图表/公式的飞书文档、挂进 Wiki 的领域节点、登记多维表格索引，并把 Feishu URL 写回本地笔记。发布前有渲染 lint 闸门，幂等且原地更新（URL 稳定，依赖本地 `.marginalia/feishu.json` 映射）。图被某些版式（首页 logo、图文并排）裁歪时，用图标记里的 `[box=x0,y0,x1,y1]` 手动指定 PDF 区域。

7. **（仅 skill 本体变更时）提交 Git。** 笔记产物（`notes/`、`.marginalia/feishu.json`、`.marginalia/figs/`）都已 gitignore，不提交。只有当本次改动了 **skill 本体**（脚本、references、SKILL.md、README）时才 commit/push，按 `references/git-workflow.md`。日常精读发表论文不产生 git 提交。

## 输出文件（Output Files）

- 笔记放 `notes/<领域>/`，文件名 `【VENUE‘YEAR】short-title.md`（如 `【NeurIPS‘2017】attention-is-all-you-need.md`）。
- 标题里用同样的前缀：`# 【VENUE‘YEAR】Paper Title`。
- venue/年份未知用 `【TBD】short-title.md`。
- 同一篇论文优先改已有笔记，不要建重复文件。

## 质量底线（Quality Bar）

- 除非论文确实拿不到，否则不要只靠 abstract 总结；只能拿到 abstract 时要明说这个限制。
- `毒舌评论` 必须明显比 TL;DR 更尖锐；如果它读起来像中性摘要，重写。
- 不要夸大 novelty；按论文自己的 framing 描述新意，并尽量和相关工作对比。
- 不要省略假设——对安全、系统、区块链类论文，假设常常决定结论是否成立。
- 公式、算法、关键定义只要是论文核心就保留，并核对记法。
- 保留证据链：关键图、表、数据、指标、ablation 都要能追溯到它们支撑的 claim。
