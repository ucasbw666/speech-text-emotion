#!/usr/bin/env python
"""Scan a Chinese speech corpus, normalize transcripts and create JSONL manifests."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import os
from pathlib import Path
import random
import sys
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.dataset import ManifestItem, write_manifest  # noqa: E402
from src.preprocessing import SUPPORTED_AUDIO_SUFFIXES  # noqa: E402
from src.text_normalization import normalize_text  # noqa: E402


SPLIT_ALIASES = {"train": "train", "dev": "dev", "valid": "dev", "validation": "dev", "test": "test"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--transcript-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data" / "manifests")
    parser.add_argument("--statistics", type=Path, default=PROJECT_ROOT / "results" / "dataset_statistics.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--dev-ratio", type=float, default=0.1)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument("--limit", type=int, help="Deterministic development subset limit.")
    return parser.parse_args()


def read_transcripts(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Return mappings by utterance id and normalized path."""

    by_id: dict[str, str] = {}
    by_path: dict[str, str] = {}
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                payload = json.loads(line)
                audio = str(payload["audio"])
                text = normalize_text(str(payload["text"]))
                by_path[Path(audio).as_posix().lower()] = text
                by_id[Path(audio).stem.lower()] = text
        return by_id, by_path

    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            stripped = line.strip()
            if not stripped:
                continue
            if "|" in stripped:
                key, text = stripped.split("|", 1)
            else:
                parts = stripped.split(maxsplit=1)
                if len(parts) != 2:
                    raise ValueError(f"Malformed transcript line {path}:{line_number}")
                key, text = parts
            normalized = normalize_text(text)
            if not normalized:
                continue
            key_path = Path(key)
            by_id[key_path.stem.lower()] = normalized
            by_path[key_path.as_posix().lower()] = normalized
    return by_id, by_path


def infer_split(path: Path) -> str | None:
    # Prefer the outermost split directory. Some AISHELL speaker archives embed
    # their original "train" path even when extracted under our dev/test split.
    for part in path.parts:
        alias = SPLIT_ALIASES.get(part.lower())
        if alias:
            return alias
    return None


def audio_metadata(path: Path) -> tuple[float, int]:
    try:
        import soundfile as sf

        info = sf.info(str(path))
        return float(info.duration), int(info.samplerate)
    except Exception:
        from src.preprocessing import load_audio

        audio = load_audio(path)
        return audio.duration_seconds, audio.sample_rate


def random_splits(items: list[ManifestItem], ratios: tuple[float, float, float], seed: int) -> list[ManifestItem]:
    order = list(range(len(items)))
    random.Random(seed).shuffle(order)
    train_end = round(len(items) * ratios[0])
    dev_end = train_end + round(len(items) * ratios[1])
    labels: dict[int, str] = {}
    for position, original_index in enumerate(order):
        labels[original_index] = "train" if position < train_end else "dev" if position < dev_end else "test"
    return [ManifestItem(**{**item.__dict__, "split": labels[index]}) for index, item in enumerate(items)]


def build_statistics(items: Iterable[ManifestItem]) -> dict[str, object]:
    rows = list(items)
    durations = [float(row.duration or 0.0) for row in rows]
    rates = Counter(row.sample_rate for row in rows if row.sample_rate)
    splits = Counter(row.split for row in rows)
    return {
        "utterances": len(rows),
        "total_duration_seconds": sum(durations),
        "total_duration_hours": sum(durations) / 3600.0,
        "average_duration_seconds": sum(durations) / len(durations) if durations else 0.0,
        "minimum_duration_seconds": min(durations, default=0.0),
        "maximum_duration_seconds": max(durations, default=0.0),
        "chinese_characters": sum(sum("\u4e00" <= char <= "\u9fff" for char in row.text) for row in rows),
        "sample_rates": {str(key): value for key, value in sorted(rates.items())},
        "split_counts": {key: splits.get(key, 0) for key in ("train", "dev", "test")},
    }


def write_statistics_table(statistics: dict[str, object], output_path: Path) -> None:
    table_path = output_path.with_suffix(".md")
    split_counts = statistics["split_counts"]
    table_path.write_text(
        "# 数据集统计\n\n"
        "| 指标 | 数值 |\n|---|---:|\n"
        f"| 语句数 | {statistics['utterances']} |\n"
        f"| 总时长（小时） | {statistics['total_duration_hours']:.4f} |\n"
        f"| 平均时长（秒） | {statistics['average_duration_seconds']:.3f} |\n"
        f"| 最短/最长（秒） | {statistics['minimum_duration_seconds']:.3f} / {statistics['maximum_duration_seconds']:.3f} |\n"
        f"| 中文字符数 | {statistics['chinese_characters']} |\n"
        f"| Train / Dev / Test | {split_counts['train']} / {split_counts['dev']} / {split_counts['test']} |\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    dataset_root = args.dataset_root.expanduser().resolve()
    transcript_file = args.transcript_file.expanduser().resolve()
    if not dataset_root.is_dir():
        raise SystemExit(f"Dataset root not found: {dataset_root}")
    if not transcript_file.is_file():
        raise SystemExit(f"Transcript file not found: {transcript_file}")
    ratio_sum = args.train_ratio + args.dev_ratio + args.test_ratio
    if abs(ratio_sum - 1.0) > 1e-6:
        raise SystemExit("train/dev/test ratios must sum to 1.0")

    by_id, by_path = read_transcripts(transcript_file)
    audio_paths = sorted(
        path for path in dataset_root.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES
    )
    if args.limit:
        audio_paths = audio_paths[: args.limit]
    items: list[ManifestItem] = []
    missing_transcripts: list[str] = []
    for audio_path in audio_paths:
        relative_key = audio_path.relative_to(dataset_root).as_posix().lower()
        text = by_path.get(relative_key) or by_id.get(audio_path.stem.lower())
        if not text:
            missing_transcripts.append(str(audio_path))
            continue
        duration, sample_rate = audio_metadata(audio_path)
        items.append(ManifestItem(
            audio=str(audio_path.resolve()),
            text=text,
            split=infer_split(audio_path.relative_to(dataset_root)),
            duration=duration,
            sample_rate=sample_rate,
        ))
    if not items:
        raise SystemExit("No matched audio/transcript pairs were found.")
    if any(item.split is None for item in items):
        items = random_splits(items, (args.train_ratio, args.dev_ratio, args.test_ratio), args.seed)

    output_dir = args.output_dir.expanduser().resolve()
    portable_items = [
        ManifestItem(
            audio=os.path.relpath(Path(item.audio), output_dir),
            text=item.text,
            split=item.split,
            duration=item.duration,
            sample_rate=item.sample_rate,
        )
        for item in items
    ]
    for split in ("train", "dev", "test"):
        count = write_manifest(
            (item for item in portable_items if item.split == split),
            output_dir / f"{split}.jsonl",
        )
        print(f"{split}: {count} samples")

    statistics = build_statistics(items)
    statistics["unmatched_audio_files"] = len(missing_transcripts)
    statistics["seed"] = args.seed
    statistics_path = args.statistics.expanduser().resolve()
    statistics_path.parent.mkdir(parents=True, exist_ok=True)
    statistics_path.write_text(json.dumps(statistics, ensure_ascii=False, indent=2), encoding="utf-8")
    write_statistics_table(statistics, statistics_path)
    print(f"Statistics: {statistics_path}")


if __name__ == "__main__":
    main()

