#!/usr/bin/env python
"""Download the pinned voice-main production model and its verified backbone."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from pathlib import Path
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
REVISION = "538403fb1940895f443904c303a0b448bbf6ab93"
REPO = "willinger566/voice-main"
BACKBONE_SHA256 = "be501a01f26fcdc7663a062dff86af839afbaef7c4de32f5e42d7e1ad2784da4"
PRODUCTION_FILES = (
    "model_config.json", "branch_0/model_config.json", "branch_0/scaler.pkl",
    "branch_0/member_0.pth", "branch_0/member_1.pth", "branch_1/model_config.json",
    "branch_1/scaler.pkl", "branch_1/member_0.pth", "branch_1/backbone_adapter.pth",
)
SAMPLE_FILES = (
    "liuchanhg_angry_236.wav", "liuchanhg_fear_207.wav", "liuchanhg_happy_205.wav",
    "liuchanhg_neutral_228.wav", "liuchanhg_sad_217.wav", "liuchanhg_surprise_233.wav",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, path: Path, expected: str | None = None) -> None:
    if path.is_file() and (sha256(path) == expected if expected else path.stat().st_size > 256):
        print(f"Already available: {path.name}", flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    for attempt in range(3):
        try:
            print(f"Downloading {path.name}", flush=True)
            with requests.get(url, stream=True, timeout=(20, 120)) as response:
                response.raise_for_status()
                last_report = time.monotonic()
                written = 0
                with partial.open("wb") as target:
                    for block in response.iter_content(2 * 1024 * 1024):
                        target.write(block)
                        written += len(block)
                        if time.monotonic() - last_report >= 15:
                            print(f"  {written / 1024**2:.1f} MiB", flush=True)
                            last_report = time.monotonic()
            if expected and sha256(partial) != expected:
                raise ValueError(f"SHA256 mismatch: {path.name}")
            partial.replace(path)
            print(f"Verified: {path.name} ({written / 1024**2:.1f} MiB)", flush=True)
            return
        except (requests.RequestException, ValueError) as exc:
            if attempt == 2:
                raise
            print(f"Retry: {exc}", flush=True)


def download_backbone(url: str, path: Path) -> None:
    """Fetch disjoint ranges into one temporary file, then verify the full hash."""
    if path.is_file() and sha256(path) == BACKBONE_SHA256:
        print("Verified existing emotion2vec backbone", flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".ranges.partial")
    probe = requests.get(url, headers={"Range": "bytes=0-0"}, stream=True, timeout=(20, 120))
    if probe.status_code != 206:
        probe.close()
        download(url, path, BACKBONE_SHA256)
        return
    size = int(probe.headers["Content-Range"].rsplit("/", 1)[1])
    resolved_url = probe.url
    probe.close()
    with partial.open("wb") as target:
        target.truncate(size)
    block_size = 16 * 1024 * 1024
    ranges = [(start, min(size - 1, start + block_size - 1)) for start in range(0, size, block_size)]

    def fetch(bounds):
        start, end = bounds
        for attempt in range(3):
            try:
                with requests.get(resolved_url, headers={"Range": f"bytes={start}-{end}"}, stream=True, timeout=(20, 90)) as response:
                    response.raise_for_status()
                    expected_range = f"bytes {start}-{end}/{size}"
                    if response.status_code != 206 or response.headers.get("Content-Range") != expected_range:
                        raise ValueError("Server returned an incorrect byte range")
                    written = 0
                    with partial.open("r+b") as target:
                        target.seek(start)
                        for block in response.iter_content(1024 * 1024):
                            if written + len(block) > end - start + 1:
                                raise ValueError("Unexpected response size")
                            target.write(block)
                            written += len(block)
                    if written != end - start + 1:
                        raise ValueError("Incomplete byte range")
                return written
            except (requests.RequestException, ValueError):
                if attempt == 2:
                    raise

    print(f"Downloading backbone: {size / 1024**2:.1f} MiB (8 connections)", flush=True)
    completed = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for future in as_completed([pool.submit(fetch, bounds) for bounds in ranges]):
            completed += future.result()
            print(f"Backbone: {completed / size:.0%}", flush=True)
    if sha256(partial) != BACKBONE_SHA256:
        raise ValueError("Backbone SHA256 mismatch")
    partial.replace(path)
    print("Verified emotion2vec backbone SHA256", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--production-only", action="store_true")
    group.add_argument("--backbone-only", action="store_true")
    args = parser.parse_args()
    base = ROOT / "models" / "emotion"
    raw_base = f"https://raw.githubusercontent.com/{REPO}/{REVISION}/models/production"
    for name in (() if args.backbone_only else PRODUCTION_FILES):
        raw_url = f"{raw_base}/{name}"
        if name.endswith((".pth", ".pkl")):
            pointer = requests.get(raw_url, timeout=30)
            pointer.raise_for_status()
            expected = next(line.split(":", 1)[1] for line in pointer.text.splitlines() if line.startswith("oid sha256:"))
            download(f"https://media.githubusercontent.com/media/{REPO}/{REVISION}/models/production/{name}", base / "production" / name, expected)
        else:
            download(raw_url, base / "production" / name)
    if not args.production_only:
        for name in ("config.yaml", "configuration.json", "tokens.txt", "model.pt"):
            url = f"https://modelscope.cn/api/v1/models/iic/emotion2vec_plus_large/repo?Revision=master&FilePath={name}"
            path = base / "emotion2vec_plus_large" / name
            if name == "model.pt":
                download_backbone(url, path)
            else:
                download(url, path)
    if not args.backbone_only:
        for name in SAMPLE_FILES:
            download(f"https://raw.githubusercontent.com/{REPO}/{REVISION}/data/samples/{name}",
                     ROOT / "assets" / "emotion_samples" / name)
    print(f"Emotion model ready: {base}", flush=True)


if __name__ == "__main__":
    main()
