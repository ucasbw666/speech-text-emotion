# 方法设计与改进候选分析

## 主流程

音频文件或麦克风输入经过重采样和单声道转换，提取 80 维 log-Mel 频谱，由 Whisper Transformer Encoder 编码；自回归 Transformer Decoder 在中文语言和转写任务提示下生成字符序列。训练、评估与 CER 计算共用同一文本规范化逻辑。

## Baseline

Baseline 使用本地保存的预训练 `openai/whisper-small`，不在课程数据上更新参数。推理强制设置中文（`zh`）和转写（`transcribe`）任务，禁用时间戳。它的优点是定义清晰、无需训练即可复现，也能衡量领域微调带来的实际收益。

## 三个改进候选

### 候选 1：数据增强 + 参数高效微调（首选）

- 音频增强：speed perturbation、random gain、可控背景噪声。
- 特征增强：SpecAugment time/frequency masking。
- 训练：Whisper-small LoRA，减少显存和 checkpoint 体积。
- 优点：实现成本可控，直接针对噪声和语速鲁棒性，可做开关消融。
- 风险：过强增强会损伤干净语音；用配置概率和强度限制，并以 dev CER 选择 checkpoint。

### 候选 2：解码语言约束

- 使用 beam search、领域关键词提示或外部中文语言模型重打分。
- 优点：无需更新声学模型，专有词可能改善明显。
- 风险：标准 Whisper 解码中接入 KenLM 成本高，且难保证公平比较；作为可选实验而非主路线。

### 候选 3：拼音感知领域纠错

- 用拼音相似度、编辑距离和受限领域词典修正同音/近音错误。
- 优点：容易展示，能解释“人工只能→人工智能”类案例。
- 风险：可能在通用测试集上误改；必须限制候选并用 test CER 验证，不能把人工挑选案例当整体提升。

## 实验后的最终选择

三组同一 test split 的真实结果为：预训练 baseline CER 26.66%，LoRA 微调（无增强）CER 6.80%，LoRA + augmentation CER 8.19%。因此最终 `Improved` 选择无增强 LoRA adapter；相对预训练 baseline 的 CER 降低率为 74.48%。

数据增强没有胜过同配置无增强微调：AISHELL 子集为安静室内、高保真、16 kHz 录音，随机速度/增益/噪声及 SpecAugment 引入的分布扰动在仅 364 条训练语句上偏强，使 CER 相对无增强版本上升 1.39 个百分点。受限拼音词典在通用测试语句上没有触发修正，CER 不变。二者均作为真实的负/中性消融结果保留，不作为最终方法。

