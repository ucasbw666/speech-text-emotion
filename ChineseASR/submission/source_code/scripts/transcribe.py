#!/usr/bin/env python
"""Transcribe one audio file with a locally stored model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.inference import WhisperASR  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model-dir", type=Path, default=PROJECT_ROOT / "models" / "asr_model")
    parser.add_argument("--adapter-dir", type=Path)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    recognizer = WhisperASR(args.model_dir, device=args.device, adapter_dir=args.adapter_dir)
    result = recognizer.transcribe(args.audio)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

