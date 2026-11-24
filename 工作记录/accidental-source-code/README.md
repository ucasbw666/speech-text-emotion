# ChineseASR

一个可本地运行、可训练、可批量评估并带 Gradio UI 的汉语连续语音识别课程项目。主模型采用 `openai/whisper-small`，所有 CER、耗时和曲线均由脚本实际生成。

## Features

- 普通话连续语音识别，输出中文文本
- WAV / MP3 / FLAC 等音频上传
- 浏览器麦克风录音
- 本地模型与 CUDA/CPU 推理，不依赖远程 ASR API
- JSONL manifest 数据管理，不重复复制大音频
- 字符级 CER、Substitution、Deletion、Insertion、RTF
- Whisper-small baseline、LoRA improved 与 augmentation ablation 实验
- 错误分析、结果图表和正式实验报告模板

## Why Whisper-small

本机为 RTX 4060 Laptop GPU（8 GB）。Whisper-small 可通过 fp16、batch size 1、梯度累积和 LoRA 进行小规模微调；Hugging Face/PyTorch 在当前 Windows 环境已验证可用。smoke test 发现 Whisper 音频输入与当前梯度检查点 hook 不兼容，因此正式 LoRA 配置关闭该选项，避免跳过 encoder 梯度。相比同时实现多个框架，单一 Whisper 路线更稳定、易解释和易复现。详细环境见 `docs/environment.md`。

## Installation

推荐：

```powershell
conda env create -f environment.yml
conda activate chinese-asr
python -m pytest
```

如果环境已由本项目创建：

```powershell
conda activate chinese-asr
python -m pip install -r requirements.txt
```

## Model Download

首次联网下载一次：

```powershell
python scripts/download_model.py
```

模型保存到 `models/asr_model/`。之后 `app.py`、推理、训练和评估都设置为读取本地文件。详见 `MODEL_DOWNLOAD.md`。

## Data Preparation

推荐公开普通话语料为 AISHELL-1。完整语料体积较大，本项目默认下载 S0002/S0003/S0004 三个说话人 archive，并分别作为 train/dev/test，避免说话人泄漏。项目不会复制音频；只生成指向原文件的 JSONL manifest。AISHELL transcript 的 `utterance_id 文本` 格式和通用 `audio_path|文本`、JSONL 均受支持。

```powershell
python scripts/download_dataset.py
python scripts/prepare_data.py `
  --dataset-root data/raw/aishell1_subset `
  --transcript-file data/raw/aishell1_subset/aishell_transcript_v0.8.txt
```

如果路径包含官方 `train/dev/test` 目录则保留官方划分，否则按固定 seed 42 划分。输出：

- `data/manifests/train.jsonl`
- `data/manifests/dev.jsonl`
- `data/manifests/test.jsonl`
- `results/dataset_statistics.json`
- `results/dataset_statistics.md`

## Baseline Inference and Evaluation

单条识别：

```powershell
python scripts/transcribe.py path\to\audio.wav --device cuda
```

批量 baseline：

```powershell
python scripts/evaluate_baseline.py --manifest data/manifests/test.jsonl --device cuda
```

结果写入 `results/baseline_results.json` 与 `results/baseline_predictions.csv`。

## Training

先运行两条样本的 smoke test：

```powershell
python scripts/train.py `
  --train_manifest data/manifests/train.jsonl `
  --dev_manifest data/manifests/dev.jsonl `
  --smoke_test
```

确认成功后再正式训练：

```powershell
python scripts/train.py `
  --train_manifest data/manifests/train.jsonl `
  --dev_manifest data/manifests/dev.jsonl `
  --config configs/improved.yaml `
  --output_dir checkpoints/improved `
  --device cuda
```

训练保存每轮 adapter、`best/`、`training_history.csv` 和 `run_metadata.json`。`improved.yaml` 是经实验选择的无增强 LoRA；`augmentation_ablation.yaml` 在完全相同训练预算下启用 speed perturbation、random gain、背景噪声与 SpecAugment，用于消融。

## Improved Evaluation

```powershell
python scripts/evaluate_improved.py --manifest data/manifests/test.jsonl --device cuda
python scripts/error_analysis.py --predictions results/improved_predictions.csv
python scripts/plot_results.py --strict
```

相对 CER 降低率定义为 `(CER_baseline - CER_improved) / CER_baseline × 100%`。只有同一 test set 的真实结果下降时，报告才会称其为性能提升。

## Run UI

```powershell
python app.py --inbrowser
```

默认只监听 `127.0.0.1:7860`，`share=False`。上传音频后点击“开始识别”；使用麦克风时，停止录音后会自动识别，也可再点击按钮重试。页面可切换 Baseline/Improved。

### 从课程提交包运行

解压 `submission/` 后，进入其中的 `source_code/` 目录执行以下命令：

```powershell
cd C:\path\to\ChineseASR_submission\source_code
conda env create -f environment.yml
conda activate chinese-asr
python scripts\download_model.py
python app.py --inbrowser
```

已有 `chinese-asr` 环境时跳过创建环境。基础 Whisper-small 权重约 1 GB，提交包没有重复包含，因此首次下载需要联网；下载完成后识别可离线运行。提交包附带的最终 LoRA adapter 位于相邻的 `model/improved_adapter/`，UI 会自动找到它，无需重新训练或手动复制。若浏览器没有自动打开，访问 `http://127.0.0.1:7860`。关闭终端中的服务可按 `Ctrl+C`。

## Project Structure

```text
ChineseASR/
├── app.py                  # Gradio 本地原型
├── configs/                # baseline/improved 配置
├── data/manifests/         # train/dev/test JSONL
├── models/                 # 本地 Whisper 模型（Git 忽略）
├── checkpoints/            # LoRA checkpoint（Git 忽略）
├── src/                    # 预处理、模型、指标、增强、纠错
├── scripts/                # 下载、数据、训练、评估、分析、绘图
├── results/                # 真实运行结果
├── report/                 # 实验报告
├── docs/                   # 环境、方法、演示文档
└── tests/                  # 自动测试
```

## Experimental Results

测试集为未参与训练或 checkpoint 选择的 AISHELL-1 S0004 说话人，共 355 条、5,041 个规范化参考字符。

| Method | CER | S | D | I | Relative CER Reduction |
|---|---:|---:|---:|---:|---:|
| Pretrained Whisper-small | 26.66% | 1,257 | 73 | 14 | — |
| LoRA + augmentation ablation | 8.19% | 371 | 41 | 1 | 69.27% |
| **LoRA improved（selected）** | **6.80%** | **325** | **17** | **1** | **74.48%** |

最终模型为无增强 LoRA。增强版本相对最终版本反而高 1.39 个 CER 百分点，说明在仅 364 条、安静室内录音的训练子集上增强强度偏大；报告如实保留这一负消融。拼音领域词典在该通用测试集上触发 0 次，CER 不变。

## Reproducibility

- 固定随机种子 42。
- 训练、验证、测试共享 `src/text_normalization.py`。
- 测试集不参与训练或 checkpoint 选择。
- 训练参数保存在 YAML，运行元数据和日志保存到文件。
- 大数据、模型和 checkpoint 由 `.gitignore` 排除，避免错误提交。

