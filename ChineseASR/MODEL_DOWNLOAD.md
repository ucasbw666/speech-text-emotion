# 模型下载与离线使用

项目只使用一个主模型：Hugging Face `openai/whisper-small`。

首次联网时执行：

```powershell
conda activate chinese-asr
python scripts/download_model.py --model-id openai/whisper-small --output-dir models/asr_model
```

脚本会同时保存模型、processor/tokenizer 和 feature extractor。下载完成后，推理脚本与 `app.py` 默认设置 `local_files_only=True`，只读取 `models/asr_model/`，不会依赖在线 API 或远程推理服务器。

模型文件体积较大，已经由 `.gitignore` 排除。提交时可以包含实际模型目录，也可以按教师要求单独压缩；不要提交 Hugging Face 全局缓存的重复副本。

