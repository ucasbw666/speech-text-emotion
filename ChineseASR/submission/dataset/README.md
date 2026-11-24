# 数据集说明

主实验采用 AISHELL-1 普通话语音数据。AISHELL-1 为开源中文 ASR 语料，Hugging Face 镜像标注为 Apache-2.0；完整语料较大，因此项目默认下载三个说话人的紧凑子集：

| Split | Speaker archive | 用途 |
|---|---|---|
| train | S0002 | LoRA 微调 |
| dev | S0003 | validation loss / checkpoint 选择 |
| test | S0004 | 最终 CER，禁止参与训练 |

这种按说话人划分避免同一说话人同时出现在训练与测试中，更适合小规模课程实验。它不是完整 AISHELL-1 官方 test benchmark，因此报告中必须写作“AISHELL-1 speaker-disjoint subset”，不能把子集 CER 冒充完整官方测试集结果。

下载并生成 manifest：

```powershell
python scripts/download_dataset.py
python scripts/prepare_data.py `
  --dataset-root data/raw/aishell1_subset `
  --transcript-file data/raw/aishell1_subset/aishell_transcript_v0.8.txt
```

音频只保留一份，manifest 使用路径引用。`data/raw/` 被 Git 忽略；submission 中默认只提供本说明、下载脚本和 manifests，避免复制占用空间。

