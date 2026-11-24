# ChineseASR 答辩演示指南

建议总时长：2–3 分钟。演示前先关闭占用显存的软件，并确认模型和两段测试音频均在本机。

## 演示前检查

```powershell
cd <ChineseASR 项目目录>
conda activate chinese-asr
python -m pytest
python scripts/transcribe.py assets/demo.wav --device cuda
```

确认 `results/baseline_results.json`、`results/improved_results.json` 和 `results/figures/baseline_vs_improved_cer.png` 来自最终同一测试集。

## 现场流程

1. 在 Terminal 中进入项目目录并执行 `conda activate chinese-asr`。
2. 执行 `python app.py --inbrowser`，浏览器打开 `http://127.0.0.1:7860`。
3. 保持 `Baseline`，用麦克风说：“人工智能正在改变我们的生活方式”，停止录音后等待自动识别。
4. 指出输出文本、音频时长、推理耗时、RTF、CUDA 设备和“完全本地推理”状态。
5. 上传准备好的较长普通话 WAV/MP3/FLAC，展示连续语音转写。
6. 若 improved checkpoint 已通过真实测试验证，切换到 `Improved` 对同一音频识别；否则不要声称个例代表总体提升。
7. 打开 `baseline_vs_improved_cer.png`，说明 CER 公式和同一 test set 上的真实结果。

## 讲解要点

- 音频被统一到 16 kHz 单声道，转为 log-Mel 特征。
- Whisper Encoder 编码声学上下文，Decoder 通过 cross-attention 自回归生成中文。
- Baseline 不在课程数据上更新；Improved 使用 LoRA 和可配置的数据增强。
- CER 使用字符级 Levenshtein 距离，分别统计替换、删除、插入。
- 模型下载一次后全部从 `models/` 加载，不调用在线 ASR 服务。

## 备用方案

- 麦克风权限失败：改用预先录好的 `assets/demo.wav`。
- CUDA 临时不可用：使用 `python scripts/transcribe.py ... --device cpu`，但预计更慢。
- Improved checkpoint 不可用：只展示 Baseline，并说明改进实验状态，禁止展示虚构结果。

