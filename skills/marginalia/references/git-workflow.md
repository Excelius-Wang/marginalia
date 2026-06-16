# 持久化、索引与提交（Git Workflow）

在一个 git 支持的论文知识库里使用时，按本流程把笔记落盘、回填索引、提交。这个文件与具体 skill 解耦，可被其他工具复用；`.agent`（Codex 用）是它的孪生精简版，两者保持一致。

## 1. 笔记落盘

- 笔记写到 `notes/<领域>/【VENUE‘YEAR】short-title.md`（领域即所用的 domain profile，如 `notes/ml/`、`notes/security/`）。
- 文件名与标题前缀一致：`# 【VENUE‘YEAR】Paper Title`。
- venue / 年份未知用 `【TBD】short-title.md`。
- 同一篇论文优先改已有笔记，不建重复文件。

## 2. 回填 README 索引

- README 里维护一个论文索引（按会议 / 年份或按主题分组）。
- 在对应分组追加或更新条目，链接到笔记文件，并保留论文 URL。
- 状态从 `TODO` 改成 `DONE` 只在笔记文件确实存在之后。
- venue / 年份未知时，放到 `Unknown / TBD` 分组，不要瞎猜。

## 3. 提交与推送

1. 跑 `git status --short`。
2. **只 stage 本次任务改动的文件**，通常是 `README.md` + `notes/<领域>/<笔记>.md` + `.marginalia/feishu.json`（飞书映射）+ 本次有意创建的论文专属素材。绝不 stage 用户的无关改动。`.marginalia/figs/` 是派生图（已 gitignore），不提交。
3. commit：新笔记用 `Add paper note: <短标题>`，修订用 `Update paper note: <短标题>`。
4. 立即 `git push`。
5. 无改动不要空 commit。push 失败要清楚报错，并保留本地 commit。
