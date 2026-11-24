#!/usr/bin/env python
"""Download a compact, speaker-disjoint AISHELL-1 subset from Hugging Face."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tarfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ID = "AISHELL/AISHELL-1"
TRANSCRIPT_FILE = "data_aishell/transcript/aishell_transcript_v0.8.txt"
DEFAULT_SPLITS = {"train": "S0002", "dev": "S0003", "test": "S0004"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data" / "raw" / "aishell1_subset")
    parser.add_argument("--keep-archives", action="store_true")
    return parser.parse_args()


def safe_extract(archive: Path, target: Path) -> None:
    target = target.resolve()
    with tarfile.open(archive, "r:gz") as handle:
        members = handle.getmembers()
        for member in members:
            destination = (target / member.name).resolve()
            if target not in destination.parents and destination != target:
                raise RuntimeError(f"Unsafe path in archive {archive}: {member.name}")
            if member.issym() or member.islnk():
                raise RuntimeError(f"Links are not allowed in dataset archive: {member.name}")
        handle.extractall(target, members=members, filter="data")


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise SystemExit("huggingface_hub is missing; install requirements.txt first.") from exc

    transcript_target = output_dir / "aishell_transcript_v0.8.txt"
    if not transcript_target.is_file():
        downloaded = Path(hf_hub_download(
            repo_id=REPO_ID,
            repo_type="dataset",
            filename=TRANSCRIPT_FILE,
            local_dir=output_dir / "downloads",
        ))
        shutil.copy2(downloaded, transcript_target)
    print(f"Transcript: {transcript_target}")

    for split, speaker in DEFAULT_SPLITS.items():
        split_dir = output_dir / split
        existing = list(split_dir.rglob("*.wav")) if split_dir.is_dir() else []
        if existing:
            print(f"{split}: reusing {len(existing)} WAV files for {speaker}")
            continue
        filename = f"data_aishell/wav/{speaker}.tar.gz"
        archive = Path(hf_hub_download(
            repo_id=REPO_ID,
            repo_type="dataset",
            filename=filename,
            local_dir=output_dir / "downloads",
        ))
        split_dir.mkdir(parents=True, exist_ok=True)
        safe_extract(archive, split_dir)
        count = len(list(split_dir.rglob("*.wav")))
        if not count:
            raise RuntimeError(f"No WAV files extracted from {archive}")
        print(f"{split}: extracted {count} WAV files for {speaker}")
        if not args.keep_archives:
            archive.unlink(missing_ok=True)

    print("Dataset subset ready.")
    print(f"Run: python scripts/prepare_data.py --dataset-root \"{output_dir}\" --transcript-file \"{transcript_target}\"")


if __name__ == "__main__":
    main()

