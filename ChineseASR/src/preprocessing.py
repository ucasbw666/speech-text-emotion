"""Audio loading and lightweight preprocessing utilities."""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from pathlib import Path

import numpy as np


SUPPORTED_AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus"}


@dataclass(frozen=True)
class AudioData:
    samples: np.ndarray
    sample_rate: int

    @property
    def duration_seconds(self) -> float:
        return float(len(self.samples) / self.sample_rate) if self.sample_rate else 0.0


def load_audio(path: str | Path, sample_rate: int = 16_000) -> AudioData:
    """Decode an audio file, convert to mono float32 and resample."""

    audio_path = Path(path).expanduser().resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")
    if audio_path.suffix.lower() not in SUPPORTED_AUDIO_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_AUDIO_SUFFIXES))
        raise ValueError(f"Unsupported audio type {audio_path.suffix!r}; expected one of: {supported}")

    try:
        import soundfile as sf
        from scipy.signal import resample_poly
    except ImportError as exc:  # pragma: no cover - exercised in installed runtime
        raise RuntimeError("Audio support is missing. Install requirements.txt first.") from exc

    try:
        samples, actual_rate = sf.read(str(audio_path), dtype="float32", always_2d=False)
    except Exception as exc:
        raise ValueError(
            f"Could not decode {audio_path}. For uncommon codecs, convert it with ffmpeg first."
        ) from exc
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim == 2:
        samples = samples.mean(axis=1, dtype=np.float32)
    elif samples.ndim != 1:
        raise ValueError(f"Unsupported audio array shape {samples.shape}: {audio_path}")
    if int(actual_rate) != sample_rate:
        divisor = gcd(int(actual_rate), sample_rate)
        samples = resample_poly(
            samples,
            up=sample_rate // divisor,
            down=int(actual_rate) // divisor,
        ).astype(np.float32)
        actual_rate = sample_rate
    if samples.size == 0:
        raise ValueError(f"Audio file is empty: {audio_path}")
    if not np.all(np.isfinite(samples)):
        raise ValueError(f"Audio contains NaN or infinite samples: {audio_path}")
    peak = float(np.max(np.abs(samples)))
    if peak > 1.0:
        samples = samples / peak
    return AudioData(samples=samples, sample_rate=int(actual_rate))

