import numpy as np

from src.augmentation import AugmentationConfig, apply_augmentation


def test_disabled_augmentation_is_identity() -> None:
    samples = np.linspace(-0.5, 0.5, 100, dtype=np.float32)
    config = AugmentationConfig(speed_probability=0, gain_probability=0, noise_probability=0)
    actual = apply_augmentation(samples, config, np.random.default_rng(42))
    np.testing.assert_allclose(actual, samples)


def test_gain_is_bounded() -> None:
    samples = np.full(100, 0.5, dtype=np.float32)
    config = AugmentationConfig(
        speed_probability=0,
        gain_probability=1,
        gain_db_min=6,
        gain_db_max=6,
        noise_probability=0,
    )
    actual = apply_augmentation(samples, config, np.random.default_rng(42))
    assert np.max(actual) <= 1.0
    assert np.mean(actual) > np.mean(samples)

