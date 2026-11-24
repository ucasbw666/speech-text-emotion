import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "outputs" / "ChineseASR"


def signature(path, crlf):
    config = json.loads(path.read_text(encoding="utf-8"))
    payload = path.read_bytes().replace(b"\r\n", b"\n")
    if crlf:
        payload = payload.replace(b"\n", b"\r\n")
    if config.get("architecture") == "audio_ensemble_v1":
        digest = hashlib.sha256(payload)
        for child in config["branches"]:
            digest.update(signature(path.parent / child["config"], crlf).encode())
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


path = ROOT / "models" / "emotion" / "production" / "model_config.json"
golden = json.loads((ROOT / "third_party" / "voice-main" / "runtime_golden.json").read_text())
print("upstream:", golden["model_signature"])
print("CRLF:", signature(path, True))
print("LF:", signature(path, False))
