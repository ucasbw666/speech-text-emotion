#!/usr/bin/env python
"""Generate report figures only from experiment files that actually exist."""

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
    parser.add_argument("--baseline-results", type=Path, default=PROJECT_ROOT / "results" / "baseline_results.json")
    parser.add_argument("--improved-results", type=Path, default=PROJECT_ROOT / "results" / "improved_results.json")
    parser.add_argument("--training-history", type=Path, default=PROJECT_ROOT / "checkpoints" / "improved" / "training_history.csv")
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "data" / "manifests" / "test.jsonl")
    parser.add_argument("--predictions", type=Path, default=PROJECT_ROOT / "results" / "baseline_predictions.csv")
    parser.add_argument("--error-analysis", type=Path, default=PROJECT_ROOT / "results" / "error_analysis.csv")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "results" / "figures")
    parser.add_argument("--strict", action="store_true", help="Fail when any required source file is missing.")
    return parser.parse_args()


def setup_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def save_loss_figures(history_path: Path, output_dir: Path, plt) -> list[Path]:
    with history_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    epochs = [int(row["epoch"]) for row in rows]
    outputs: list[Path] = []
    for field, filename, label in (
        ("train_loss", "train_loss.png", "Training Loss"),
        ("validation_loss", "val_loss.png", "Validation Loss"),
    ):
        fig, axis = plt.subplots(figsize=(7, 4.5))
        axis.plot(epochs, [float(row[field]) for row in rows], marker="o")
        axis.set(title=label, xlabel="Epoch", ylabel="Loss")
        axis.grid(alpha=0.3)
        fig.tight_layout()
        path = output_dir / filename
        fig.savefig(path, dpi=180)
        plt.close(fig)
        outputs.append(path)
    return outputs


def save_cer_comparison(baseline_path: Path, improved_path: Path, output_dir: Path, plt) -> Path:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    improved = json.loads(improved_path.read_text(encoding="utf-8"))
    fig, axis = plt.subplots(figsize=(6, 4.5))
    values = [float(baseline["cer"]) * 100, float(improved["cer"]) * 100]
    bars = axis.bar(["Baseline", "Improved"], values, color=["#6b8afd", "#4bb38a"])
    axis.bar_label(bars, fmt="%.2f%%")
    axis.set(title="Baseline vs Improved CER", ylabel="CER (%)")
    axis.set_ylim(0, max(values + [1]) * 1.2)
    fig.tight_layout()
    path = output_dir / "baseline_vs_improved_cer.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def save_duration_distribution(manifest: Path, output_dir: Path, plt) -> Path:
    items = read_manifest(manifest)
    durations = [item.duration for item in items if item.duration is not None]
    if not durations:
        raise ValueError("Manifest has no duration metadata; rerun scripts/prepare_data.py")
    fig, axis = plt.subplots(figsize=(7, 4.5))
    axis.hist(durations, bins=min(30, max(5, round(len(durations) ** 0.5))), color="#6b8afd", edgecolor="white")
    axis.set(title="Audio Duration Distribution", xlabel="Duration (seconds)", ylabel="Utterances")
    axis.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = output_dir / "audio_duration_distribution.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def save_inference_time(predictions: Path, output_dir: Path, plt) -> Path:
    with predictions.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fig, axis = plt.subplots(figsize=(7, 4.5))
    axis.scatter(
        [float(row["duration_seconds"]) for row in rows],
        [float(row["inference_seconds"]) for row in rows],
        alpha=0.7,
        color="#4bb38a",
    )
    axis.set(title="Inference Time by Audio Duration", xlabel="Audio duration (seconds)", ylabel="Inference time (seconds)")
    axis.grid(alpha=0.3)
    fig.tight_layout()
    path = output_dir / "inference_time.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def save_error_types(error_analysis: Path, output_dir: Path, plt) -> Path:
    from collections import Counter

    with error_analysis.open("r", encoding="utf-8-sig", newline="") as handle:
        counts = Counter(row["error_type"] for row in csv.DictReader(handle))
    fig, axis = plt.subplots(figsize=(8, 4.5))
    labels, values = zip(*counts.most_common()) if counts else (["无错误"], [0])
    axis.bar(labels, values, color="#f2a65a")
    axis.set(title="Error Type Distribution", xlabel="Error type", ylabel="Cases")
    axis.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    path = output_dir / "error_type_distribution.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def main() -> None:
    args = parse_args()
    plt = setup_matplotlib()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    jobs = [
        ((args.training_history,), lambda: save_loss_figures(args.training_history, output_dir, plt)),
        ((args.baseline_results, args.improved_results), lambda: [save_cer_comparison(args.baseline_results, args.improved_results, output_dir, plt)]),
        ((args.manifest,), lambda: [save_duration_distribution(args.manifest, output_dir, plt)]),
        ((args.predictions,), lambda: [save_inference_time(args.predictions, output_dir, plt)]),
        ((args.error_analysis,), lambda: [save_error_types(args.error_analysis, output_dir, plt)]),
    ]
    created: list[Path] = []
    for required, job in jobs:
        missing = [path for path in required if not path.is_file()]
        if missing:
            message = "Missing source data: " + ", ".join(str(path) for path in missing)
            if args.strict:
                raise SystemExit(message)
            print(f"SKIP: {message}")
            continue
        created.extend(job())
    for path in created:
        print(f"Created: {path}")


if __name__ == "__main__":
    main()

