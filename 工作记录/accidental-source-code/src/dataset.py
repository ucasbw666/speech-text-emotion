"""Manifest I/O and validation shared by training and evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Iterable, Iterator


@dataclass(frozen=True)
class ManifestItem:
    audio: str
    text: str
    split: str | None = None
    duration: float | None = None
    sample_rate: int | None = None

    def resolved_audio(self, manifest_path: str | Path) -> Path:
        path = Path(self.audio).expanduser()
        if not path.is_absolute():
            path = Path(manifest_path).resolve().parent / path
        return path.resolve()


def read_manifest(path: str | Path, *, require_audio: bool = True) -> list[ManifestItem]:
    manifest_path = Path(path).expanduser().resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    items: list[ManifestItem] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                item = ManifestItem(
                    audio=str(payload["audio"]),
                    text=str(payload["text"]),
                    split=payload.get("split"),
                    duration=float(payload["duration"]) if payload.get("duration") is not None else None,
                    sample_rate=int(payload["sample_rate"]) if payload.get("sample_rate") is not None else None,
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid JSONL at {manifest_path}:{line_number}: {exc}") from exc
            if require_audio and not item.resolved_audio(manifest_path).is_file():
                raise FileNotFoundError(
                    f"Audio referenced at {manifest_path}:{line_number} does not exist: "
                    f"{item.resolved_audio(manifest_path)}"
                )
            items.append(item)
    if not items:
        raise ValueError(f"Manifest contains no samples: {manifest_path}")
    return items


def iter_manifest(path: str | Path, *, require_audio: bool = True) -> Iterator[ManifestItem]:
    yield from read_manifest(path, require_audio=require_audio)


def write_manifest(items: Iterable[ManifestItem], path: str | Path) -> int:
    manifest_path = Path(path).expanduser().resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in items:
            payload = {key: value for key, value in asdict(item).items() if value is not None}
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            count += 1
    return count

