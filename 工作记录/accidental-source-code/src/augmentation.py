"""Low-cost waveform augmentation for the improved experiment."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AugmentationConfig:
    speed_probability: float = 0.4
    speed_min: float = 0.9
    speed_max: float = 1.1
    gain_probability: float = 0.4
    gain_db_min: float = -6.0
    gain_db_max: float = 6.0
    noise_probability: float = 0.3
    snr_db_min: float = 10.0
    snr_db_max: float = 25.0


def _chance(rng: np.random.Generator, probability: float) -> bool:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("augmentation probabilities must be within [0, 1]")
    return bool(rng.random() < probability)


def speed_perturb(samples: np.ndarray, rate: float) -> np.ndarray:
    if rate <= 0:
        raise ValueError("speed rate must be positive")
    try:
        from scipy.signal import resample
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("scipy is required for speed perturbation") from exc
    output_length = max(1, round(len(samples) / rate))
    return np.asarray(resample(samples.astype(np.float32), output_length), dtype=np.float32)


def apply_augmentation(
    samples: np.ndarray,
    config: AugmentationConfig,
    rng: np.random.Generator,
) -> np.ndarray:
    """Apply independently sampled speed, gain and Gaussian-noise transforms."""

    augmented = np.asarray(samples, dtype=np.float32).copy()
    if _chance(rng, config.speed_probability):
        augmented = speed_perturb(augmented, float(rng.uniform(config.speed_min, config.speed_max)))
    if _chance(rng, config.gain_probability):
        gain_db = float(rng.uniform(config.gain_db_min, config.gain_db_max))
        augmented *= 10.0 ** (gain_db / 20.0)
    if _chance(rng, config.noise_probability):
        signal_rms = float(np.sqrt(np.mean(np.square(augmented)) + 1e-12))
        snr_db = float(rng.uniform(config.snr_db_min, config.snr_db_max))
        noise_rms = signal_rms / (10.0 ** (snr_db / 20.0))
        augmented += rng.normal(0.0, noise_rms, size=augmented.shape).astype(np.float32)
    return np.clip(augmented, -1.0, 1.0).astype(np.float32)

