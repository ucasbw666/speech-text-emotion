#!/usr/bin/env python
"""Download one Whisper snapshot for later fully offline inference."""

from __future__ import annotations

import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default="openai/whisper-small")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "models" / "asr_model")
    parser.add_argument("--revision", default="main")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    if (output_dir / "config.json").is_file():
        print(f"Model already present; reusing: {output_dir}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise SystemExit("huggingface_hub is missing; install requirements.txt first.") from exc

    print(f"Downloading {args.model_id} to {output_dir}")
    snapshot_download(
        repo_id=args.model_id,
        revision=args.revision,
        local_dir=output_dir,
        allow_patterns=[
            "*.json",
            "*.txt",
            "*.model",
            "*.safetensors",
            "*.py",
        ],
    )
    print(f"Download complete. Offline model directory: {output_dir}")


if __name__ == "__main__":
    main()

