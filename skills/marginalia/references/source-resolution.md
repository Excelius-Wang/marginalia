# 来源解析（Source Resolution）

把用户给的任意来源解析成可读全文，并提取干净的元数据。这个文件与具体 skill 解耦，可被其他工具复用。

## 输入类型与处理

- **本地 PDF**：直接读。记录本地路径。
- **arXiv 链接 / id**（`arxiv.org/abs/xxxx`、`arxiv.org/pdf/xxxx`、`xxxx.xxxxx`）：取 abstract 页与 PDF；arXiv id 是稳定标识，记录下来。
- **DOI**（`doi.org/...` 或 `10.xxxx/...`）：解析到出版社页面，尽量拿到官方 PDF 或 HTML 全文。
- **OpenReview**：取 forum 页的论文与元数据，必要时连 review 一起看。
- **出版社 / 会议 / 项目页 / 作者主页**：打开并定位到论文本体或可下载 PDF。
- **GitHub 链接**：通常是 artifact / 代码；从 README 找配套论文链接，再回到上面的流程。
- **只有标题**：先 web 搜 canonical 版本，优先 arXiv 或官方会议版；找到多个版本时优先正式出版版，并记录版本差异。

## 抓取策略

- 先抓全文再分析。拿不到全文、只能拿到 abstract 时，明确声明分析是临时的，并标出哪些部分无法验证。
- 在 git 知识库里工作时，先搜 `README.md` 和 `notes/`，确认是否已有同一篇论文的笔记或本地副本，避免重复。

## 元数据提取

抽取 Title、Authors、Venue、Year、Paper URL、Code、Dataset / Artifact，以及 arXiv id / DOI 等稳定标识。

任何不确定的字段标 `Unknown` 或 `TBD` + 一句原因。**绝不编造** venue、年份、code、dataset 或 claim。会议 / 年份未知时，文件名与索引用 `【TBD】`。
