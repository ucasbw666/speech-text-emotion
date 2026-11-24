#!/usr/bin/env python
"""Exercise both real models via the unified UI's public API."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from gradio_client import Client, handle_file

ROOT = Path(__file__).resolve().parents[1]


def windows_bundle_signature(path):
    """The upstream reference was recorded with Windows CRLF JSON files."""
    config = json.loads(path.read_text(encoding="utf-8"))
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    if config.get("architecture") == "audio_ensemble_v1":
        digest = hashlib.sha256(payload)
        for branch in config["branches"]:
            digest.update(windows_bundle_signature(path.parent / branch["config"]).encode())
        return digest.hexdigest()
    files = [path, path.parent / config.get("scaler", "scaler.pkl")]
    files.extend(path.parent / m.get("checkpoint", "best_model.pth") for m in config.get("members", [config]))
    if config.get("backbone_adapter"):
        files.append(path.parent / config["backbone_adapter"])
    digest = hashlib.sha256()
    for file in files:
        digest.update(file.name.encode())
        digest.update(payload if file == path else file.read_bytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:7860")
    args = parser.parse_args()
    client = Client(args.url)
    golden = json.loads((ROOT / "third_party/voice-main/runtime_golden.json").read_text(encoding="utf-8"))
    references = {Path(item["path"]).name: item["expected"] for item in golden["samples"]}
    production = ROOT / "models/emotion/production/model_config.json"
    if not production.is_file():
        production = ROOT.parent / "model/emotion_production/model_config.json"
    signature = windows_bundle_signature(production)
    assert signature == golden["model_signature"], "Production artifacts differ from the pinned upstream model"
    records = []
    probability_differences = []
    for filename in ("liuchanhg_angry_236.wav", "liuchanhg_happy_205.wav", "liuchanhg_sad_217.wav"):
        path = ROOT / "assets" / "emotion_samples" / filename
        result = client.predict(handle_file(str(path)), "Improved", "文字 + 情绪", api_name="/analyze")
        details = result[-1]
        assert result[0] and result[1], result[-2]
        assert not details["errors"], details["errors"]
        probabilities = details["emotion"]["all_probabilities"]
        assert len(probabilities) == 6 and abs(sum(probabilities.values()) - 1) < 1e-5
        assert details["emotion"]["segments"]
        assert details["emotion"]["predicted_id"] == references[filename]["prediction"]
        probability_differences.append(max(abs(value - references[filename]["probabilities"][name])
                                           for name, value in probabilities.items()))
        records.append({"file": filename, "text": result[0], "emotion": result[1], "confidence_percent": result[2],
                        "total_seconds": result[8], "details": details})
        print(json.dumps({key: value for key, value in records[-1].items() if key != "details"}, ensure_ascii=False), flush=True)
    demo = ROOT / "assets" / "demo.wav"
    for model in ("Baseline", "Improved"):
        result = client.predict(handle_file(str(demo)), model, api_name="/recognize")
        assert len(result) == 5 and result[0], result
    for mode in ("仅文字", "仅情绪"):
        result = client.predict(handle_file(str(demo)), "Improved", mode, api_name="/analyze")
        details = result[-1]
        assert not details["errors"], details
        assert (details["transcription"] is not None) == (mode == "仅文字")
        assert (details["emotion"] is not None) == (mode == "仅情绪")
    destination = ROOT / "results" / "joint_ui_verification.json"
    destination.write_text(json.dumps({"status": "passed", "joint_samples": records,
                                      "legacy_asr_api": "Baseline and Improved passed", "single_modes": "passed",
                                      "upstream_windows_signature": signature,
                                      "upstream_probability_max_difference": max(probability_differences),
                                      "comparison_note": "Upstream signature includes raw JSON bytes; CRLF normalization matches the Windows reference. Probabilities may vary slightly with torch/hardware."},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Joint UI verification passed: {destination}")


if __name__ == "__main__":
    main()
