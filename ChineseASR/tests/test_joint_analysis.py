from pathlib import Path

import pytest

import app
from src.inference import TranscriptionResult


@pytest.fixture
def fake_models(monkeypatch):
    calls = []

    class ASR:
        def transcribe(self, path):
            calls.append(("asr", path))
            return TranscriptionResult(path, "今天很开心", "今天很开心", 3.0, .3, .1, "cpu")

    class Emotion:
        def predict(self, path):
            calls.append(("emotion", path))
            return {
                "predicted_emotion": "happy", "confidence": .8,
                "all_probabilities": {"neutral": .04, "happy": .8, "sad": .04, "angry": .04, "fear": .04, "surprise": .04},
                "segments": [{"start": 0, "end": 3, "predicted_emotion": "happy", "confidence": .8}],
                "audio": {"duration": 3.0, "warnings": []}, "device": "cpu", "interpretation": "测试结果",
            }

    monkeypatch.setattr(app, "get_recognizer", lambda _: ASR())
    monkeypatch.setattr(app, "get_emotion_recognizer", lambda: Emotion())
    return calls


def test_joint_runs_both_on_same_audio_and_streams_results(fake_models):
    updates = list(app.analyze("same.wav", "Improved", "文字 + 情绪"))
    final = updates[-1]
    assert len(updates) == 3
    assert sorted(fake_models) == [("asr", "same.wav"), ("emotion", "same.wav")]
    assert final[0:3] == ("今天很开心", "高兴", 80.0)
    assert sum(final[3].values()) == pytest.approx(1)
    assert final[4] == [[0, 3, "高兴", 80.0]]
    assert final[-1]["errors"] == {}


@pytest.mark.parametrize("mode,expected", [("仅文字", "asr"), ("仅情绪", "emotion")])
def test_single_mode_does_not_load_other_model(fake_models, mode, expected):
    list(app.analyze("same.wav", "Baseline", mode))
    assert fake_models == [(expected, "same.wav")]


def test_missing_audio_never_loads_models(fake_models):
    result = list(app.analyze(None, "Improved"))[-1]
    assert fake_models == []
    assert "请先上传" in result[-2]


def test_emotion_failure_preserves_transcription(fake_models, monkeypatch):
    def fail():
        raise FileNotFoundError("情绪模型缺失")
    monkeypatch.setattr(app, "get_emotion_recognizer", fail)
    final = list(app.analyze("same.wav", "Improved"))[-1]
    assert final[0] == "今天很开心"
    assert "情绪模型缺失" in final[-2]
    assert "情绪识别" in final[-1]["errors"]


def test_asr_failure_preserves_emotion(fake_models, monkeypatch):
    def fail(_):
        raise FileNotFoundError("文字模型缺失")
    monkeypatch.setattr(app, "get_recognizer", fail)
    final = list(app.analyze("same.wav", "Improved"))[-1]
    assert final[0] == ""
    assert final[1] == "高兴"
    assert "文字识别" in final[-1]["errors"]


def test_vendor_runtime_imports_without_global_model_name_collision():
    from src.emotion_backend.model import summarize_probabilities
    from src import model as asr_model
    result = summarize_probabilities([.1, .5, .1, .1, .1, .1])
    assert result["predicted_emotion"] == "happy"
    assert hasattr(asr_model, "load_whisper_pipeline")
