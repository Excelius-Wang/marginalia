---
name: marginalia
description: 深度精读学术论文，产出结构化的中文研究笔记，带批判性分析——重建作者思路、机制层面讲清方法、找出最脆弱的假设、设计反例、提出非增量的 follow-up 研究方向，把笔记沉淀进 git 知识库（notes/ + README 索引），并可发布成带图表/公式的飞书文档（Wiki 知识库 + 多维表格索引）。当用户给出论文标题、DOI、arXiv/OpenReview/出版社/GitHub/PDF 链接或本地 PDF，或要求 精读/阅读/总结/分析/批判/复现/归纳贡献/比较相关工作/设计反例/提出后续研究/维护论文索引/发布到飞书/同步到飞书，或要 read / summarize / critique / deep-read a paper、design a minimal reproduction or counterexample、propose follow-up research、publish to Feishu 时使用。适用于 ML、NLP、CV、systems、安全、区块链、生物、经济等领域。
---

# Marginalia 论文精读

## 概览（Overview）

用这个 skill 把一篇论文变成一份**可长期复用的中文研究笔记**，而不是一段松散摘要。三个优先级：事实落地、显式标注不确定性、和用户已有知识库建立连接。

精读不是复述 abstract。真正的贡献和真正的问题往往藏在 method、实验细节、图表、limitations 和 appendix 里。

这个 skill 把"深度主动阅读"和"持久化知识库"合在一起：

- **主动阅读**——重建作者思路、讲清核心 intuition、找出最脆弱的假设、设计反例、提出后续研究。
- **持久化**——按统一模板写成 markdown 笔记，落到 `notes/`，回填 README 索引，并 commit/push。

按需阅读以下 reference（渐进式披露，不要一次全读）：

- 解析论文来源 → `references/source-resolution.md`
- 阅读与分析流程 → `references/reading-method.md`
- 写笔记的输出模板 → `references/note-schema.md`
- 写作风格与信息来源纪律 → `references/style-guide.md`
- 领域标签与子领域分类法 → `references/domains/<领域>.md`
- 笔记落盘、索引、提交 → `references/git-workflow.md`
- 发布到飞书（Wiki 文档 + 多维表格索引）→ `references/feishu-publish.md`

## 工作流（Workflow）

1. **解析来源。** 按 `references/source-resolution.md` 把标题/DOI/arXiv/OpenReview/PDF/GitHub/本地 PDF 解析成可读全文。在知识库里先搜 `README.md` 和 `notes/`，避免对同一篇论文重复建笔记。记录来源 URL 与访问路径。元数据不确定就标 `Unknown`/`TBD`，绝不编造 venue、年份、code、dataset 或 claim。

2. **判定领域，加载 profile。** 根据论文内容（或用户指定）判断领域，读对应的 `references/domains/<领域>.md` 拿到 `Scope/子领域` 分类法和标签词表；判断不了就用 `general.md`。

3. **深度阅读与分析。** 按 `references/reading-method.md` 执行：三遍阅读 → 校准 novelty → 重建作者思路 → 批判性综合。全程按 `references/style-guide.md` 的四类信息来源纪律标注（论文声称 / 已有文献 / 合理推断 / 不确定猜测）。

4. **写中文笔记。** 用 `references/note-schema.md` 的模板。重点写好招牌段落：`毒舌评论`、`作者思路重建`、`最脆弱的假设`、`最小复现实验`、`最强反例设计`、`Follow-up Research Idea`。分清"作者展示的"和"你推出的"。在 `Key Artifacts` 里给关键图/表打 `[p.N]` 页码标记（供发布时抽图），并给最能概览全文的那张图加 `[hero]`；关键公式用 `$...$` 内联以便渲染。**写的同时就做排版判断**：按 `references/style-guide.md` 的语义纪律给核心论断加粗 `**…**`、给专名/机制/指标/优势/风险打彩色标记 `{{b|p|o|g|r:词}}`（不同颜色不同作用），这是写作的一部分，不要留到发布再补。

5. **落盘与回填。** 按 `references/git-workflow.md`：笔记写到 `notes/<领域>/【VENUE‘YEAR】short-title.md`，回填 README 索引（`TODO`→`DONE` 并链接到笔记文件）。

6. **发布到飞书。** 按 `references/feishu-publish.md` 跑 `python3 skills/marginalia/scripts/publish_to_feishu.py "<note>" --pdf <pdf>`：生成带图表/公式的飞书文档、挂进 Wiki 的领域节点、登记多维表格索引，并把 Feishu URL 写回笔记。幂等；失败不阻塞本地提交。

7. **同步到 Git。** 在 git 知识库里，只 stage 本次任务改动的文件（含 `.marginalia/feishu.json` 映射），commit（`Add paper note: <短标题>` 或 `Update paper note: ...`），再 `git push`。无改动不空 commit；push 失败要清楚报错并保留本地 commit。

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
