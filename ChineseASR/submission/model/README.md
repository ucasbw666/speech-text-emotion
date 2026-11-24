# Model files

`improved_adapter/` 是最终选用的 LoRA checkpoint（test CER 6.80%）。`augmentation_ablation_adapter/` 是增强消融（CER 8.19%）。两者均需配合 `openai/whisper-small` 基模型；运行 source_code/scripts/download_model.py 获取基模型。预训练基模型约 1 GB，为避免提交包重复膨胀未复制到此目录。

`emotion_production/` 为 voice-main 的原始情绪双分支模型。情绪骨干约 1.81 GiB，请在 source_code 中运行 `python scripts/download_emotion_model.py` 下载和校验。统一 UI 自动查找本目录中的 ASR adapter 与情绪 production。来源和原许可见 source_code/third_party/voice-main/。
