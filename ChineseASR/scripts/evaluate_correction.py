#!/usr/bin/env python
"""Evaluate conservative domain-lexicon homophone correction on saved predictions."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.correction import load_lexicon, pinyin_correct  # noqa: E402
from src.metrics import corpus_cer, levenshtein_counts  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=PROJECT_ROOT / "results" / "improved_predictions.csv")
    parser.add_argument("--lexicon", type=Path, default=PROJECT_ROOT / "assets" / "domain_lexicon.txt")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "results" / "corrected_predictions.csv")
    parser.add_argument("--results", type=Path, default=PROJECT_ROOT / "results" / "correction_results.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    lexicon = load_lexicon(args.lexicon)
    with args.predictions.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    original_pairs: list[tuple[str, str]] = []
    corrected_pairs: list[tuple[str, str]] = []
    total_changes = 0
    for row in rows:
        corrected, changes = pinyin_correct(row["prediction"], lexicon)
        counts = levenshtein_counts(row["reference"], corrected, normalize=False)
        original_pairs.append((row["reference"], row["prediction"]))
        corrected_pairs.append((row["reference"], corrected))
        row["raw_prediction"] = row["prediction"]
        row["prediction"] = corrected
        row["corrections"] = "; ".join(f"{item.before}->{item.after}" for item in changes)
        row["cer"] = counts.cer
        row["substitutions"] = counts.substitutions
        row["deletions"] = counts.deletions
        row["insertions"] = counts.insertions
        total_changes += len(changes)
    original = corpus_cer(original_pairs, normalize=False)
    corrected = corpus_cer(corrected_pairs, normalize=False)
    summary = {
        "original": original.to_dict(),
        "corrected": corrected.to_dict(),
        "corrections_applied": total_changes,
        "absolute_cer_change": corrected.cer - original.cer,
        "lexicon_entries": len(lexicon),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    args.results.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

