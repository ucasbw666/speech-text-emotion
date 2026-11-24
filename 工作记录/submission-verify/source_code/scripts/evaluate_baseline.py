#!/usr/bin/env python
"""Batch-evaluate the local pretrained Whisper baseline."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.dataset import read_manifest  # noqa: E402
from src.inference import WhisperASR  # noqa: E402
from src.metrics import corpus_cer, levenshtein_counts  # noqa: E402
from src.text_normalization import normalize_text  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, default=PROJECT_ROOT / "models" / "asr_model")
    parser.add_argument("--adapter-dir", type=Path)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--results", type=Path, default=PROJECT_ROOT / "results" / "baseline_results.json")
    parser.add_argument("--predictions", type=Path, default=PROJECT_ROOT / "results" / "baseline_predictions.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    items = read_manifest(args.manifest)
    if args.limit:
        items = items[: args.limit]
    recognizer = WhisperASR(args.model_dir, device=args.device, adapter_dir=args.adapter_dir)
    rows: list[dict[str, object]] = []
    pairs: list[tuple[str, str]] = []
    started = perf_counter()
    for index, item in enumerate(items, start=1):
        audio_path = item.resolved_audio(args.manifest)
        result = recognizer.transcribe(audio_path)
        reference = normalize_text(item.text)
        prediction = normalize_text(result.text)
        counts = levenshtein_counts(reference, prediction, normalize=False)
        pairs.append((reference, prediction))
        rows.append({
            "audio_path": str(audio_path),
            "reference": reference,
            "prediction": prediction,
            "cer": counts.cer,
            "substitutions": counts.substitutions,
            "deletions": counts.deletions,
            "insertions": counts.insertions,
            "duration_seconds": result.duration_seconds,
            "inference_seconds": result.inference_seconds,
            "real_time_factor": result.real_time_factor,
        })
        print(f"[{index}/{len(items)}] CER={counts.cer:.4f} {audio_path.name}")

    total_elapsed = perf_counter() - started
    overall = corpus_cer(pairs, normalize=False)
    summary = {
        **overall.to_dict(),
        "samples": len(rows),
        "device": recognizer.device,
        "total_inference_seconds": sum(float(row["inference_seconds"]) for row in rows),
        "wall_clock_seconds": total_elapsed,
        "average_inference_seconds": statistics.fmean(float(row["inference_seconds"]) for row in rows),
        "average_real_time_factor": statistics.fmean(float(row["real_time_factor"]) for row in rows),
        "manifest": str(args.manifest.resolve()),
        "model_dir": str(args.model_dir.resolve()),
    }
    args.predictions.parent.mkdir(parents=True, exist_ok=True)
    with args.predictions.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    args.results.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

