# 实验环境记录

检查时间：2026-10-02（Asia/Shanghai）

## 硬件与系统

| 项目 | 检查结果 |
|---|---|
| 操作系统 | Windows 11, build 10.0.26200.9457, x64 |
| CPU | 13th Gen Intel(R) Core(TM) i9-13900HX，32 逻辑处理器 |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU |
| 显存 | 8188 MiB（PyTorch 报告 8.0 GiB） |
| NVIDIA Driver | 560.94 |
| 驱动支持的最高 CUDA | 12.6（`nvidia-smi`） |
| 当前可用内存 | 约 3015 MB（检查瞬间；总内存查询受当前执行权限限制） |
| C 盘 | 已用 181.74 GB，可用 18.26 GB |
| D 盘 | 已用 219.31 GB，可用 185.11 GB |
| E 盘 | 已用 176.21 GB，可用 171.01 GB |

## Python 与深度学习环境

系统 PATH 中的 `python.exe`/`pip.exe` 指向 Microsoft Store alias，当前不可执行。Conda 可用：

| 项目 | 检查结果 |
|---|---|
| Conda | 24.9.2，安装于 `D:\\Anaconda` |
| Conda base Python | 3.12.7 |
| 可复用环境 | `prml`，Python 3.11.13 |
| PyTorch | 2.5.1（`prml`） |
| PyTorch CUDA | 12.1 |
| cuDNN | 9.1.0（PyTorch API 返回 90100） |
| CUDA 可用 | 是 |
| Transformers | 4.57.5 |
| Gradio | 6.1.0 |

`prml` 环境已有 CUDA PyTorch、Transformers、Gradio、NumPy、Pandas、Matplotlib、PyYAML 和 Accelerate，但缺少项目所需的音频/数据/测试依赖。为避免污染已有课程环境，项目文档以创建专用 `chinese-asr` 环境为标准流程；开发阶段可先在 `prml` 中运行不缺依赖的检查。

## 模型路线选择

选择 Hugging Face `openai/whisper-small`，原因如下：

1. 现有 Windows CUDA 环境已经验证 Transformers 与 PyTorch 可用。
2. Whisper 的 log-Mel、Transformer Encoder-Decoder、cross-attention 与自回归解码过程适合课程报告讲解。
3. 8 GB 显存可通过 fp16、batch size 1、梯度累积和 LoRA 进行小规模微调；smoke test 后因音频输入 hook 警告关闭梯度检查点。
4. 模型下载一次后可从 `models/asr_model/` 完全离线推理。
5. 与同时维护 FunASR 和 Whisper 相比，单一路线更容易测试、复现与现场展示。

## 推荐运行方式

```powershell
conda env create -f environment.yml
conda activate chinese-asr
python -m pytest
```

如果 `python` 仍命中 Windows alias，可直接使用：

```powershell
conda run -n chinese-asr python -m pytest
```

## 复核命令

```powershell
nvidia-smi
conda --version
conda run -n chinese-asr python --version
conda run -n chinese-asr python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda)"
Get-PSDrive -PSProvider FileSystem
```

