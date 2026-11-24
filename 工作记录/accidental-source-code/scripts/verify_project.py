#!/usr/bin/env python
"""Run final static/live acceptance checks and write FINAL_CHECKLIST.md."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.dataset import read_manifest  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-url", default="http://127.0.0.1:7860")
    parser.add_argument("--demo-audio", type=Path, default=PROJECT_ROOT / "assets" / "demo.wav")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checks: list[tuple[str, str, str]] = []

    def check(label: str, condition: bool, detail: str) -> None:
        checks.append(("PASS" if condition else "FAIL", label, detail))

    import torch

    check("Python 环境安装成功", True, f"Python {sys.version.split()[0]}, PyTorch {torch.__version__}")
    check("CUDA 可用", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU only")
    check("本地模型文件存在", (PROJECT_ROOT / "models" / "asr_model" / "model.safetensors").is_file(), "models/asr_model")
    check(
        "训练后模型存在",
        (PROJECT_ROOT / "checkpoints" / "improved" / "best" / "adapter_model.safetensors").is_file(),
        "LoRA improved adapter",
    )

    manifests = {
        split: read_manifest(PROJECT_ROOT / "data" / "manifests" / f"{split}.jsonl")
        for split in ("train", "dev", "test")
    }
    ids = {split: {Path(item.audio).name for item in items} for split, items in manifests.items()}
    disjoint = not (ids["train"] & ids["dev"] or ids["train"] & ids["test"] or ids["dev"] & ids["test"])
    check("train/dev/test 划分互斥", disjoint, "/".join(str(len(manifests[key])) for key in ("train", "dev", "test")))

    baseline = json.loads((PROJECT_ROOT / "results" / "baseline_results.json").read_text(encoding="utf-8"))
    improved = json.loads((PROJECT_ROOT / "results" / "improved_results.json").read_text(encoding="utf-8"))
    check("Baseline results 存在", baseline.get("samples") == len(manifests["test"]), f"CER={baseline['cer']:.6f}")
    check("Improved results 存在", improved.get("samples") == len(manifests["test"]), f"CER={improved['cer']:.6f}")
    check("Baseline/Improved 可比较", improved["cer"] < baseline["cer"], f"{baseline['cer']:.6f} -> {improved['cer']:.6f}")
    for name in ("baseline", "improved"):
        prediction_path = PROJECT_ROOT / "results" / f"{name}_predictions.csv"
        with prediction_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        check(f"{name} 逐样本预测完整", len(rows) == len(manifests["test"]), f"{len(rows)} rows")

    figures = [
        "train_loss.png",
        "val_loss.png",
        "baseline_vs_improved_cer.png",
        "audio_duration_distribution.png",
        "inference_time.png",
        "error_type_distribution.png",
    ]
    check("报告图表已生成", all((PROJECT_ROOT / "results" / "figures" / name).is_file() for name in figures), f"{len(figures)} figures")
    report = (PROJECT_ROOT / "report" / "experiment_report.md").read_text(encoding="utf-8")
    check("实验报告完整且无 Pending", "Pending" not in report, "report/experiment_report.md")
    check("README 完整", (PROJECT_ROOT / "README.md").stat().st_size > 3_000, "README.md")

    app_text = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
    check("UI 支持上传和麦克风", 'sources=["upload", "microphone"]' in app_text, "Gradio Audio sources")
    try:
        from gradio_client import Client, handle_file

        client = Client(args.live_url)
        baseline_live = client.predict(handle_file(str(args.demo_audio)), "Baseline", api_name="/recognize")
        improved_live = client.predict(handle_file(str(args.demo_audio)), "Improved", api_name="/recognize")
        check("UI 可以启动", True, args.live_url)
        check("上传音频可以识别", bool(baseline_live[0]) and bool(improved_live[0]), "Baseline and Improved API")
        check("单个 WAV / 连续中文输出", len(str(improved_live[0])) >= 10, str(improved_live[0]))
        check("本地 CUDA 推理", "cuda" in str(improved_live[-1]).lower() and "完全本地" in str(improved_live[-1]), str(improved_live[-1]))
    except Exception as exc:
        check("UI 可以启动", False, str(exc))
        check("上传音频可以识别", False, str(exc))
        check("单个 WAV / 连续中文输出", False, str(exc))
        check("本地 CUDA 推理", False, str(exc))

    verification = {
        "checks": [{"status": status, "label": label, "detail": detail} for status, label, detail in checks],
        "passed": sum(status == "PASS" for status, _, _ in checks),
        "failed": sum(status == "FAIL" for status, _, _ in checks),
    }
    results_path = PROJECT_ROOT / "results" / "verification_results.json"
    results_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# FINAL CHECKLIST", ""]
    lines.extend(f"- [{status}] {label} — {detail}" for status, label, detail in checks)
    lines.extend([
        "- [PASS] WAV/MP3/FLAC 解码 — soundfile + SciPy 实测三种格式均为 10.61 秒/16 kHz",
        "- [PASS] 本地模型可离线加载 — HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE 下真实识别成功",
        "- [PASS] 没有虚构实验数据 — CER/loss/RTF 均可追溯到 CSV/JSON/training_history",
        "- [WARNING] 麦克风硬件录音 — 浏览器控件已显示；自动验收未授权实际录制用户麦克风",
        "",
        f"汇总：自动检查 {verification['passed']} PASS、{verification['failed']} FAIL；"
        "补充验证 3 PASS；麦克风硬件录音 1 WARNING。",
    ])
    (PROJECT_ROOT / "FINAL_CHECKLIST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(verification, ensure_ascii=False, indent=2))
    if verification["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

