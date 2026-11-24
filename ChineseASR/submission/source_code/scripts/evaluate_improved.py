#!/usr/bin/env python
"""Evaluate a local Whisper LoRA adapter using the same baseline protocol."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "evaluate_baseline.py"),
        *sys.argv[1:],
    ]
    if "--adapter-dir" not in sys.argv:
        command.extend(["--adapter-dir", str(PROJECT_ROOT / "checkpoints" / "improved" / "best")])
    if "--results" not in sys.argv:
        command.extend(["--results", str(PROJECT_ROOT / "results" / "improved_results.json")])
    if "--predictions" not in sys.argv:
        command.extend(["--predictions", str(PROJECT_ROOT / "results" / "improved_predictions.csv")])
    raise SystemExit(subprocess.call(command))


if __name__ == "__main__":
    main()

