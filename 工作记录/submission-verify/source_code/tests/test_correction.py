from src.correction import pinyin_correct


def test_exact_pinyin_domain_correction() -> None:
    corrected, changes = pinyin_correct("人工只能正在发展", ["人工智能"])
    assert corrected == "人工智能正在发展"
    assert changes[0].before == "人工只能"


def test_does_not_change_unrelated_text() -> None:
    corrected, changes = pinyin_correct("今天天气很好", ["人工智能"])
    assert corrected == "今天天气很好"
    assert changes == []

