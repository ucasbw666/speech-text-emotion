#!/usr/bin/env python
"""Rank high-CER samples and assign reproducible heuristic error categories."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "results" / "error_analysis.csv")
    parser.add_argument("--top-k", type=int, default=20)
    return parser.parse_args()


def has_homophone_substitution(reference: str, prediction: str) -> bool:
    if len(reference) != len(prediction):
        return False
    try:
        from pypinyin import Style, lazy_pinyin
    except ImportError:
        return False
    differing = [(ref, hyp) for ref, hyp in zip(reference, prediction) if ref != hyp]
    if not differing:
        return False
    return all(
        lazy_pinyin(ref, style=Style.NORMAL) == lazy_pinyin(hyp, style=Style.NORMAL)
        for ref, hyp in differing
    )


def classify(row: dict[str, str]) -> str:
    reference = row["reference"]
    prediction = row["prediction"]
    substitutions = int(float(row.get("substitutions", 0)))
    deletions = int(float(row.get("deletions", 0)))
    insertions = int(float(row.get("insertions", 0)))
    duration = float(row.get("duration_seconds", 0) or 0)
    if re.search(r"[0-9零〇一二两三四五六七八九十百千万亿点百分]", reference) and reference != prediction:
        return "数字识别错误"
    if re.search(r"[A-Za-z]", reference) and reference != prediction:
        return "中英文混合错误"
    if has_homophone_substitution(reference, prediction):
        return "同音字替换"
    if duration >= 15.0:
        return "长语音错误"
    if deletions > max(substitutions, insertions):
        return "漏字"
    if insertions > max(substitutions, deletions):
        return "插字"
    if substitutions:
        return "替换错误"
    return "混合错误"


def main() -> None:
    args = parse_args()
    with args.predictions.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    erroneous = [row for row in rows if float(row["cer"]) > 0]
    erroneous.sort(key=lambda row: (float(row["cer"]), float(row.get("duration_seconds", 0))), reverse=True)
    selected = erroneous[: args.top_k]
    for rank, row in enumerate(selected, start=1):
        row["rank"] = rank
        row["error_type"] = classify(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not selected:
        args.output.write_text("rank,error_type,audio_path,reference,prediction,cer\n", encoding="utf-8-sig")
        print("No recognition errors found.")
        return
    priority = ["rank", "error_type", "audio_path", "reference", "prediction", "cer"]
    remaining = [key for key in selected[0] if key not in priority]
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=priority + remaining)
        writer.writeheader()
        writer.writerows(selected)
    print(f"Saved {len(selected)} cases to {args.output.resolve()}")


if __name__ == "__main__":
    main()

