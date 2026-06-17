# 产物边界与提交规范（Git Workflow）

这个 skill 的**正式产物是飞书文档**：每篇精读发布成飞书文档，挂进飞书知识库（Wiki 按领域建树），并在飞书多维表格（Base）登记可筛选索引。**知识库与索引都在飞书，不在 git。** 这个文件与具体 skill 解耦，可被其他工具复用；`.agent`（Codex 用）是它的孪生精简版，两者保持一致。

## 1. 产物分两层

- **正式产物（飞书）**：文档 + Wiki 节点 + Base 索引行。唯一的知识库与索引，对外分享、可筛选。
- **运行期缓存（本地，gitignore，不提交）**：
  - `notes/<领域>/【VENUE‘YEAR】short-title.md` —— agent 写作的自然产物 + 发布脚本的输入；保留它才能本地 grep、重发、原地更新。文件名与标题前缀一致 `# 【VENUE‘YEAR】Paper Title`；venue/年份未知用 `【TBD】short-title.md`；同一篇论文优先改已有文件，不建重复。
  - `.marginalia/feishu.json` —— 幂等映射（doc_id / node_token / record_id / hash），支撑「原地更新同一篇飞书文档、URL 不变」。本机有效；换机器丢了就退化为新建。
  - `.marginalia/figs/` —— 从 PDF 派生的图，可随时重抽。

## 2. 去重与更新（不靠 README）

- 开始前查**飞书 Base 索引**（或本地 `notes/` 缓存）有没有同一篇，避免重复建文档。
- 有就走**原地更新**（发布脚本据本地 `feishu.json` 自动判断并 overwrite 同一篇，URL 不变）。
- 不再维护 README 论文索引——筛选/检索在飞书 Base 上做。

## 3. 提交与推送（只提交 skill 本体）

日常精读发表论文**不产生 git 提交**（笔记、映射、派生图都已 gitignore）。只有当你**改了 skill 本体**才提交：

1. 跑 `git status --short`，确认改动只涉及 skill 本体——`skills/marginalia/`（脚本、references、SKILL.md）、`README.md` / `README.zh-CN.md`、`.agent`、`.gitignore` 等。
2. **只 stage 本次有意改动的文件**，绝不 stage 用户的无关改动，也绝不强加 `notes/`、`.marginalia/feishu.json`、`.marginalia/figs/`（它们已 gitignore）。
3. commit：用描述这次 skill 改动的信息（如 `Improve figure extraction`、`Add domain profile: security`）。
4. 立即 `git push`。
5. 无改动不要空 commit。push 失败要清楚报错，并保留本地 commit。
