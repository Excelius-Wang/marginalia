# 发布到飞书（Feishu Publish）

把一篇本地 md 笔记发布成一篇飞书文档（带图表、公式、表格），挂进飞书知识库（Wiki），并在飞书多维表格（Base）索引里登记一行。**飞书文档是正式产物、Base 是唯一索引**；本地 md 只是 gitignore 的运行期中间产物（agent 写作的自然产出 + 脚本输入 + 可本地 grep/重发），不进 git。脚本确定性、幂等。

## 前置

- 已安装 `lark-cli`（`/opt/homebrew/bin/lark-cli`）。
- 已登录用户身份：`lark-cli auth status` 显示 `identities.user.available = true`。否则：

  ```bash
  lark-cli auth login --scope "docs:document.content:read docx:document:create docx:document:write_only docs:document.media:upload wiki:node:create base:table:create base:record:create base:record:update drive:file:upload"
  ```
- **图表抽取后端**：优先 **PyMuPDF（fitz）几何定位**——读 PDF 的矢量绘图/图像/文字块坐标来圈定图，矢量图和位图一视同仁，比"渲染后猜像素"稳得多。装在项目级 venv 里（避开 PEP 668、不污染系统）：

  ```bash
  python3 -m venv .marginalia/venv && .marginalia/venv/bin/pip install pymupdf pdf2image Pillow
  ```
  发布脚本用这个 python 跑（才能用上 fitz）：`.marginalia/venv/bin/python skills/marginalia/scripts/publish_to_feishu.py ...`。没装 fitz 时自动退回 poppler（`pdftotext`/`pdftoppm` + Pillow）启发式。

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

`extract_figures.py` 定位图：fitz 后端找到以 “Figure N / Table N” 开头的 caption 行,再取其上方矢量绘图+图像块的并集(并用上方文字块钳住顶部),`clip` 渲染该区域。**难例**：首页有 logo/页眉等杂散图形、或图文并排(图在文字旁)的版式,纯几何会过裁——这类用下面的 `[box=...]` 手动指定。再普适的零样本方案需要版面检测模型(DocLayout-YOLO 等)或 pdffigures2,属于更重的依赖。

**手动兜底 `[box=x0,y0,x1,y1]`**(PDF 点坐标)：在图标记里写,如 `Fig.7 [p.11] [box=335,200,545,455] MaPE 示意:…`,脚本直接裁这个框,绕过所有启发式。

**版面（借鉴 Notion paper-reading 模板的形式）**：

- **顶部导读 callout**：脚本自动在文档最前插一个 `📖 导读` 块（无需在 md 里写），含两行：**配色图例**（蓝专名/紫机制/橙指标/绿优势/红批判，让读者能解码正文彩色）+ **速读路径**（一句话总结 → 毒舌评论 → 核心直觉 → 最脆弱的假设，赶时间只看这几节）。飞书已按 heading 自动生成大纲侧栏，故这里只做导向、不重复列全部小节。hero 头图紧随其后。
- **顶部 banner**：给最能概览全文的那张图（通常是架构总览）在标记后加 `[hero]`，例如 `Fig.6 [p.9] [hero] 架构总览：…`。脚本会把它以 720px 居中插到正文最前（首节之前）。
- **图穿插正文**：给图加 `[@锚文本]` 锚点（一段正文里**唯一**的短句），脚本用 `--selection-with-ellipsis` 把它插到那个块之后，例如 `Fig.1 [p.1] [@各任务反而互相增益] 雷达图：…`。没标 `[@...]` 的图统一落到文末「图表」节。
- **描述性 caption**：图的 caption 自动取 `[p.N]`（及标记）之后的那段描述文字，并加「图N/表N」前缀，不再是干巴巴的 "Figure 1"。
- **小节之间自动插分隔线**（`<hr/>`），标题彩色加粗承担视觉节奏。

## 原创绘图（用飞书画板）

本脚本只从 PDF 抽取**论文已有**的图。若要补一张**论文里没有、需要自己画**的示意图（概念图 / 流程图 / 架构对比 / 时序图 / 思维导图等），**优先用飞书画板**（`lark-whiteboard` / `lark-whiteboard-cli` skill）直接在飞书文档里画，而不是 ASCII 图、mermaid 源码或外部图床——画板是飞书原生对象，随文档协作、可再编辑、清晰度可控。把它当作正文里的一张图来安排位置（参照上面的图穿插约定）。

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

**知识库交叉链接**：笔记里指向库内另一篇笔记的相对 `.md` 链接（如 `[On-Policy SFT](【arXiv‘2026】towards-on-policy-sft.md)`），发布时脚本按 `feishu.json` 映射把 href **重写成目标笔记的飞书 URL**——因为飞书会静默丢弃非 http 的相对 href。本地 md 保持可移植的相对路径（GitHub/本地可跳转），只有飞书渲染产物用 URL。目标笔记尚未发布时链接原样保留；目标发布后对本篇 `--force` 重发即可让链接生效。

**纪律（照搬 pretty-lark-doc）**：每个 callout 只在各自小节出现一次且彼此远离，故 2–3 语义色的克制原则仍成立；emoji 用默认 emoji 呈现的字符（避免带变体选择符的 `⚠️`）。发布后用 `lark-cli docs +fetch --doc <id> --doc-format xml --detail full` 核对：颜色会被飞书规范化为 `rgb(...)`，确认 callout/grid/table 块数与配色都在。

> 改了渲染逻辑后重发已有笔记要加 `--force`：内容哈希忽略渲染、只看 md 正文，正文没改不会自动重发。

## 公式

md 里用 `$...$`（行内）或 `$$...$$`（展示）包裹的会转成飞书 `<latex>`。

**金额里的 `$` 要转义**：`$...$` 一律当作行内公式（包括数字开头的 `$2^{n}$`、`$3\times3$`），所以字面美元符号写成 `\$`（如 `\$173`、`\$0.75/M`）或直接用「美元」。漏转义时，裸 `$` 会和后面的 `$` 配对、把中间的中文正文吞成一条公式——发布前的 latex 校验会**抓到「公式片段含中文」并 fail-loud**（几乎一定是未转义的金额），据此改成 `\$` 或「美元」即可，不会静默发出坏文档。

**发布前有公式结构校验门禁（fail-loud）**：`lint_latex` 对每个公式片段查花括号、`\left`/`\right`、`\begin`/`\end` 配对与空公式，挂了**中止发布**并报出问题片段。只做结构校验、不本地编译——避免严格本地引擎（如 mathtext）误杀飞书能渲染的合法 KaTeX，所以零误报。写错的 `\frac{a}{b`（少右括号）会被拦下，而合法的 `\right.`（隐形定界符）不会误报。

## 飞书组织

- **Wiki**：默认用个人知识库 `my_library`（创建独立共享空间需组织管理员权限，脚本会自动回退到 `my_library`）。按 `notes/<domain>/` 的 domain 建一个节点（如 `ml`），论文文档挂在该 domain 节点下。
- **Base 索引**：一个多维表格 `marginalia 论文索引`，表 `Papers`，字段：Title / Authors / Venue / Year / Domain / Tags / Status / Paper / Feishu / Note。以 `Note`（笔记相对路径）为业务主键。

## 幂等与映射

`.marginalia/feishu.json`（**本地运行期映射，gitignore，不提交**）记录：`wiki_space_id`、`domain_nodes`、`base_token`、`table_id`、以及每篇 `notes[path] = {doc_id, url, record_id, hash}`。它支撑「原地更新同一篇飞书文档、URL 不变」——本机有效；换机器丢了就退化为新建（跨机器更新可后续加「从飞书 Base 反向重建映射」的工具）。

- 笔记内容（忽略自动写回的 `- Feishu Doc:` 行）哈希未变 → 跳过（除非 `--force`）。
- 变更 → **原地更新**同一篇文档（`docs +update --command overwrite` 清空正文后分块 `append` 重写，再重插图片），**URL 保持不变**。仅首次发布或旧文档已被删时才新建并挂进 Wiki。
- Base 行按 `Note` 主键更新（不新建重复行）；映射存 `doc_id`/`node_token`/`record_id`/`hash`。
- 发布成功后把飞书文档 URL 写回笔记 Metadata 的 `- Feishu Doc:` 行。

## 失败兜底

- 发布失败应清楚报错，但不影响本地 md 的写入（本地 md 是 gitignore 缓存，本就不提交）。
- lark-cli 命令可能在 JSON 前打印进度行，脚本 `lark()` 会切出 JSON 段再解析。

## 已知局限（v1）

- 向量复合图自动裁剪不完美。
- 图穿插靠 `[@锚文本]` 手动指定（锚文本要在正文里唯一）；未标的图落到文末「图表」节。
- 公式用 `<latex>`（行内/单独成段）；飞书无独立公式块。
- 嵌套列表支持两层。表格用 `<colgroup>` 撑满页宽。
