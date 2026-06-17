# 发布到飞书（Feishu Publish）

把一篇本地 md 笔记发布成一篇飞书文档（带图表、公式、表格），挂进飞书知识库（Wiki），并在飞书多维表格（Base）索引里登记一行。md 仍是版本化的*源*，飞书是*渲染产物*。脚本确定性、幂等。

## 前置

- 已安装 `lark-cli`（`/opt/homebrew/bin/lark-cli`）。
- 已登录用户身份：`lark-cli auth status` 显示 `identities.user.available = true`。否则：

  ```bash
  lark-cli auth login --scope "docs:document.content:read docx:document:create docx:document:write_only docs:document.media:upload wiki:node:create base:table:create base:record:create base:record:update drive:file:upload"
  ```
- 图表抽取依赖 poppler（`pdftotext`/`pdftoppm`）+ `pdf2image` + `Pillow`（均为脚本运行环境已具备）。无需 PyMuPDF。

## 用法

在仓库根目录运行（lark-cli 要求 `--file` 为相对 cwd 的路径）：

```bash
python3 skills/marginalia/scripts/publish_to_feishu.py "notes/<domain>/<note>.md" --pdf /path/to/paper.pdf
```

- `--pdf` 省略则只发文字（不抽图）。
- `--dry-run` 只打印将要创建的 DocxXML 与图表清单，不调用 lark-cli。
- `--force` 即使内容未变也重发。

## 图表约定（关键）

脚本从笔记 `## Key Artifacts` 节里解析**页码标记**来决定抽哪些图。写笔记时给关键图/表打 `[p.N]`：

```
- Fig.1 [p.1] 雷达图：...
- Fig.6 [p.9] 架构总览：...
- Table 1 [p.2] 任务覆盖矩阵：...
```

脚本（`extract_figures.py`）按 caption 定位 + 行/列墨迹密度裁剪：`pdftotext -bbox` 找 “Figure N / Table N” caption 的坐标，`pdf2image` 渲染该页，向上跳过 caption→图之间的空白、再找图上方的空白带定出图顶，并按列分栏选出 caption 所在的那一栏（处理双栏/侧边图）。

**版面（借鉴 Notion paper-reading 模板的形式）**：

- **顶部 banner**：给最能概览全文的那张图（通常是架构总览）在标记后加 `[hero]`，例如 `Fig.6 [p.9] [hero] 架构总览：…`。脚本会把它以 720px 居中插到正文最前（首节之前），像论文头图。未标 `[hero]` 则没有头图。
- **其余关键图**聚到文档末尾的「图表 Figures」节，按序、带 caption。
- **小节之间自动插分隔线**（`<hr/>`），与 callout 一起承担视觉节奏（标题保持黑色，不额外染色，避免与语义色打架）。

## 语义渲染（页面美观）

脚本不是把 md 平铺成灰色段落，而是按**固定小节标题**做语义路由，套用飞书的彩色块（参考开源 skill `pretty-lark-doc` 的渲染层）。保持 `note-schema.md` 的标准标题，美化才会触发：

| 小节标题（前缀匹配） | 渲染 | 颜色 / emoji |
| --- | --- | --- |
| `Metadata` | 两列表格（字段名灰底加粗） | gray |
| `TL;DR` | callout | 蓝 💡 |
| `毒舌评论` | callout | 红 🔴 |
| `核心 Intuition` | callout | 紫 ✨ |
| `最脆弱的假设` | callout | 橙 ❗ |
| `My Takeaways` | callout | 绿 ✅ |
| `Follow-up Research Idea` | callout | 紫 🚀 |
| `Strengths` + `Limitations`（相邻） | 左右并排 grid，各自 callout | 绿 ✅ / 橙 🚧 |
| 其余小节 | 普通标题 + 块 | — |

**章节标题彩色**：每个 `## ` 标题渲染成彩色（callout 小节用其语义色，其余蓝色），呼应参考排版的彩色标题。

**正文内联语义色**：笔记里 `{{c:词}}` 标记渲染成彩色文本，`c` ∈ `b`蓝/`p`紫/`o`橙/`g`绿/`r`红，不同颜色不同含义（专名/机制/指标/优势/风险），由写笔记的人按 `style-guide.md` 的纪律主动判断打标——这是写作的一部分，不是机械正则。`**加粗**` 只给核心论断主干。颜色可与加粗叠加（`{{r:**…**}}`）。

通用块也补齐了：GFM 管道表格 `| … |`（表头灰底）→ `<table>`、有序列表 `1.` → `<ol seq="auto">`、`` `code` ``、链接、`<hr>`、两层嵌套列表。

**纪律（照搬 pretty-lark-doc）**：每个 callout 只在各自小节出现一次且彼此远离，故 2–3 语义色的克制原则仍成立；emoji 用默认 emoji 呈现的字符（避免带变体选择符的 `⚠️`）。发布后用 `lark-cli docs +fetch --doc <id> --doc-format xml --detail full` 核对：颜色会被飞书规范化为 `rgb(...)`，确认 callout/grid/table 块数与配色都在。

> 改了渲染逻辑后重发已有笔记要加 `--force`：内容哈希忽略渲染、只看 md 正文，正文没改不会自动重发。

## 公式

md 里用 `$...$` 包裹的会转成飞书内联 `<latex>`。飞书 v2 只支持**内联** latex；多行/展示公式 v1 作为纯文本/代码呈现（精确渲染成图是后续项）。

## 飞书组织

- **Wiki**：默认用个人知识库 `my_library`（创建独立共享空间需组织管理员权限，脚本会自动回退到 `my_library`）。按 `notes/<domain>/` 的 domain 建一个节点（如 `ml`），论文文档挂在该 domain 节点下。
- **Base 索引**：一个多维表格 `marginalia 论文索引`，表 `Papers`，字段：Title / Authors / Venue / Year / Domain / Tags / Status / Paper / Feishu / Note。以 `Note`（笔记相对路径）为业务主键。

## 幂等与映射

`.marginalia/feishu.json`（提交进 git）记录：`wiki_space_id`、`domain_nodes`、`base_token`、`table_id`、以及每篇 `notes[path] = {doc_id, url, record_id, hash}`。

- 笔记内容（忽略自动写回的 `- Feishu Doc:` 行）哈希未变 → 跳过（除非 `--force`）。
- 变更 → 删除旧文档后重建，Base 行按 `Note` 主键更新（不新建重复行）。每篇映射额外存 `node_token`：删旧文档走 `wiki +node-delete --obj-type wiki --yes`（文档已挂进 Wiki，必须按 *node* token 删，不能用 docx obj token，也不能用 `drive +delete`）。
- 发布成功后把飞书文档 URL 写回笔记 Metadata 的 `- Feishu Doc:` 行。
- 注意：删除-重建会换新的文档 URL（脚本已自动写回笔记与映射）。内容没变时不重发，URL 即保持稳定。

## 失败兜底

- 发布在 git commit 之前完成；发布失败应清楚报错，但不阻塞本地 md 的写入与提交。
- lark-cli 命令可能在 JSON 前打印进度行，脚本 `lark()` 会切出 JSON 段再解析。

## 已知局限（v1）

- 向量复合图自动裁剪不完美；除 `[hero]` 头图外，其余图聚在「图表」节而非穿插到讨论处。
- 仅内联公式；展示公式 best-effort。
- 嵌套列表支持两层。
