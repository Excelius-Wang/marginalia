# 领域 Profile：ML / NLP / CV / Systems

机器学习及其系统类论文用这个 profile。

## Scope / Subfield（取论文真正的小方向）

例：`语言模型预训练`、`指令微调 / RLHF`、`检索增强 (RAG)`、`高效注意力 / 长上下文`、`扩散模型`、`多模态对齐`、`模型压缩 / 量化`、`推理加速 / serving`、`表示学习`、`分布式训练`、`数据集 / benchmark 构建`、`可解释性`、`鲁棒性 / 对抗`。

## Tags（按论文实际取 3–8 个）

`Pretraining`、`Fine-tuning`、`RLHF`、`In-context Learning`、`Retrieval`、`Attention`、`Transformer`、`Diffusion`、`Multimodal`、`Architecture`、`Optimization`、`Scaling Laws`、`Efficiency`、`Quantization`、`Distillation`、`Benchmark`、`Dataset`、`Evaluation`、`Interpretability`、`Robustness`、`Reasoning`、`Agents`。

## 领域专用批判提示

- baseline 是否包含最新、最强对手？是否在同等算力 / 数据下比较？
- 提升来自方法本身，还是更多算力 / 更多数据 / 更长训练 / 调参？有没有对应的 ablation 把它们分开？
- 评测有没有数据泄漏（test set 进了 pretraining、或选择性报告）？
- benchmark 是否已饱和或被 game？指标和真实能力的 gap 有多大？
- 复现成本（算力、数据、闭源依赖）是否现实？
- 声称的泛化范围是否被实验覆盖，还是只在窄设定上验证？
