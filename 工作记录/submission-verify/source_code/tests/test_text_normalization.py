from src.text_normalization import NormalizationConfig, normalize_text


def test_normalize_chinese_and_width() -> None:
    assert normalize_text(" 人工 智能，ＡＳＲ！ ") == "人工智能asr"


def test_keep_digits_remove_symbols() -> None:
    assert normalize_text("版本 ２.０ © 2026") == "版本202026"


def test_optional_whitespace() -> None:
    config = NormalizationConfig(remove_whitespace=False)
    assert normalize_text("  中  文 ASR ", config) == "中 文 asr"

