"""Local adapter for the pinned voice-main speech-emotion ensemble."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMOTION_LABELS = {
    "neutral": "中性", "happy": "高兴", "sad": "悲伤",
    "angry": "愤怒", "fear": "恐惧", "surprise": "惊讶",
}


class SpeechEmotionRecognizer:
    def __init__(self, model_root: str | Path | None = None, device: str = "auto"):
        import torch

        base = Path(model_root or os.getenv("EMOTION_MODEL_ROOT", ROOT / "models" / "emotion"))
        # Packaged production weights live alongside source_code, like the ASR adapter.
        production = base / "production" / "model_config.json"
        packaged = ROOT.parent / "model" / "emotion_production" / "model_config.json"
        if not production.is_file() and packaged.is_file():
            production = packaged
        backbone = base / "emotion2vec_plus_large"
        if not production.is_file() or not (backbone / "model.pt").is_file():
            raise FileNotFoundError("缺少情绪模型，请先运行 python scripts/download_emotion_model.py。")
        self.device = ("cuda" if torch.cuda.is_available() else "cpu") if device == "auto" else device
        from .emotion_backend.inference import EmotionRecognizer

        self.recognizer = EmotionRecognizer(
            emotion2vec_model=str(backbone), config_path=production, device=self.device,
        )

    def predict(self, audio_path: str | Path) -> dict:
        result = self.recognizer.predict(str(audio_path))
        return {**result, "device": self.device, "model_signature": self.recognizer.signature}
