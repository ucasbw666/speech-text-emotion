import pytest

from src.metrics import cer, corpus_cer, levenshtein_counts


def test_substitution() -> None:
    counts = levenshtein_counts("人工智能", "人工只能")
    assert counts.substitutions == 1
    assert counts.deletions == 0
    assert counts.insertions == 0
    assert counts.reference_characters == 4
    assert counts.cer == pytest.approx(0.25)


def test_deletion_and_insertion() -> None:
    deletion = levenshtein_counts("连续语音", "连续音")
    insertion = levenshtein_counts("中文", "中语文")
    assert deletion.deletions == 1
    assert insertion.insertions == 1


def test_normalization_is_shared() -> None:
    assert cer("你好，世界！", "你 好 世 界") == 0.0


def test_corpus_aggregation() -> None:
    counts = corpus_cer([("中文", "中问"), ("识别", "识别啊")])
    assert counts.reference_characters == 4
    assert counts.substitutions == 1
    assert counts.insertions == 1
    assert counts.cer == pytest.approx(0.5)

