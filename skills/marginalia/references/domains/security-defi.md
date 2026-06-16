# 领域 Profile：安全 / 区块链 / DeFi

安全、区块链、DeFi 类论文用这个 profile。源自 paper-reading-workflow 的 DeFi 分类法，并放宽到一般安全。

## Scope / Subfield（取论文真正的小方向）

例：`攻击检测`、`全范围恶意检测`、`攻击溯源`、`价格操纵检测`、`MEV 测量`、`套利检测`、`Rug Pull 检测`、`图方法检测`、`规则判断检测`、`形式化验证`、`经济安全分析`、`借贷清算风险`、`跨链攻击分析`、`智能合约漏洞`、`模糊测试 / fuzzing`、`隐私 / 匿名性`。

## Tags（按论文实际取 3–8 个）

`MEV`、`DEX`、`AMM`、`Oracle`、`Flash Loan`、`Arbitrage`、`Lending`、`Liquidation`、`Stablecoin`、`Cross-chain`、`Rug Pull`、`Formal Methods`、`Measurement`、`Attack Detection`、`Smart Contract`、`Fuzzing`、`Static Analysis`、`Transaction Analysis`、`Rule-based Detection`、`Privacy`。

## 领域专用批判提示（安全类论文的假设常常决定结论是否成立）

- 威胁模型是否清晰、是否现实？攻击者能力是否被过度限制或过度放大？
- 链上 / 链下假设，以及市场 / 流动性 / 排序 / 预言机 / 网络假设是否成立？
- 检测方法是否依赖预定义模式 / 规则？对未来变体、跨交易、非标准 token 的鲁棒性如何？
- 数据集 / ground truth 是怎么来的？是否人工标注、是否可复核、是否有偏？
- 误报 / 漏报来源是否被分析？precision / recall 的权衡在真实部署里意味着什么？
- 经济假设（gas 成本、套利修正、清算激励）是否被纳入？
