# 语音文字与情绪联合识别

## 本机打开

```powershell
cd D:\语音大作业\ChineseASR
conda activate chinese-asr
python app.py --inbrowser
```

浏览器打开 http://127.0.0.1:7860 。服务运行时保留终端，结束时按 Ctrl+C。

## 新电脑准备

在包含 app.py 的目录执行：

```powershell
conda env create -f environment.yml
conda activate chinese-asr
python scripts/download_model.py
python scripts/download_emotion_model.py
python app.py --inbrowser
```

情绪下载脚本从 voice-main 固定 commit 获取原始 production 模型，按 Git LFS SHA256 验证；从 ModelScope 下载原始 emotion2vec+ large 骨干，并校验训练配置要求的 SHA256。首次下载需要网络，之后模型推理在本机完成。

已有本项目旧环境时，先安装与 PyTorch 2.5.1 / CUDA 12.1 匹配的音频包，再更新依赖：

```powershell
conda install -n chinese-asr -c pytorch -c nvidia torchaudio=2.5.1 pytorch=2.5.1 pytorch-cuda=12.1
python -m pip install -r requirements.txt
python scripts/download_emotion_model.py
```

## 操作

1. 上传音频，或允许浏览器麦克风权限并录音；停止录音会自动分析。
2. 保持“文字 + 情绪”，点击“开始联合分析”。上传文件后需手动点击按钮。
3. 左侧查看中文转写；右侧查看主要情绪、模型置信度和完整六类概率。
4. 展开“分段情绪与详细结果”查看每个时间段及原始联合 JSON。
5. 可切换“仅文字”或“仅情绪”分别使用两项功能。清空按钮移除音频和结果，保留模型与任务选择。

文字模型 Baseline 为预训练 Whisper-small，Improved 为原项目的中文 LoRA。情绪模型是 voice-main 原始的冻结/微调双分支概率融合，不是关键词匹配，也不从文字内容推断情绪。情绪分析保留原模型的 0.5–60 秒限制，建议单人、无背景音乐、3–10 秒语音。超过范围时仍可返回成功的文字结果。

并行任务共用同一个输入文件，分别执行各自的预处理。首次任务耗时包含模型加载；后续复用缓存。总等待时间包含加载与本次回调处理，不等于两个并行任务耗时之和。文字 RTF 只统计 Whisper 推理时间 / 音频时长。

## 提交包

`submission/source_code/` 是运行目录。最终 Whisper LoRA 自动从 `../model/improved_adapter/` 读取；情绪 production 自动从 `../model/emotion_production/` 读取。两个大骨干未复制到提交包：在 source_code 中执行上面的两个模型下载脚本后即可运行。无需手动修改 app.py 的路径。

## 常见情况

- 缺少情绪模型：运行 `python scripts/download_emotion_model.py`；仍可选“仅文字”。
- 麦克风无权限：从 localhost 网页打开，并在浏览器中允许麦克风。
- 音频过短、静音或超过 60 秒：情绪模型会给出具体原因，文字任务独立保留结果。
- 7860 已被占用：使用 `python app.py --port 7861 --inbrowser`，浏览器访问对应端口。
- 情绪不明确：页面会保留原模型的低置信度提示；置信度不是正确率。

## 代码

- `app.py`：统一组件、并行任务、增量结果、原文字 API 兼容。
- `src/emotion.py`：情绪路径解析及结果封装。
- `src/emotion_backend/`：上游模型、声学特征、音频预处理及融合推理。
- `scripts/download_emotion_model.py`：固定版本与哈希校验下载。
- `third_party/voice-main/`：来源、上游说明及数据许可。

## 验证

保持网页服务运行，在另一个已激活环境的终端执行：

```powershell
python scripts/verify_joint_ui.py
# 可选浏览器检查：使用已安装的 Edge，不需要另行下载浏览器
python -m pip install playwright
python scripts/browser_joint_smoke.py
```

API 检查包括三个真实样例的文字/情绪、上游模型签名、两种单独模式及原文字 API。浏览器检查实际上传并点击按钮，截图保存在 `report/figures/joint_ui_screenshot.png`。这属于功能验收，不作为新的情绪准确率评测。
