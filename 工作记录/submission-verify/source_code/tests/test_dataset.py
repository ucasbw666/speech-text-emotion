import json
from pathlib import Path

import pytest

from src.dataset import ManifestItem, read_manifest, write_manifest


def test_manifest_round_trip(tmp_path: Path) -> None:
    audio = tmp_path / "example.wav"
    audio.write_bytes(b"RIFF")
    manifest = tmp_path / "test.jsonl"
    write_manifest([ManifestItem(str(audio), "你好", "test", 1.0, 16000)], manifest)
    items = read_manifest(manifest)
    assert items[0].text == "你好"
    assert items[0].resolved_audio(manifest) == audio.resolve()


def test_manifest_rejects_missing_audio(tmp_path: Path) -> None:
    manifest = tmp_path / "test.jsonl"
    manifest.write_text(json.dumps({"audio": "missing.wav", "text": "你好"}), encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        read_manifest(manifest)

