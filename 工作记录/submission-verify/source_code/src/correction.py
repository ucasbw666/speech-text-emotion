"""Conservative pinyin-aware correction constrained by a domain lexicon."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Correction:
    before: str
    after: str
    start: int
    end: int


def load_lexicon(path: str | Path) -> list[str]:
    lexicon_path = Path(path).expanduser().resolve()
    if not lexicon_path.is_file():
        raise FileNotFoundError(f"Domain lexicon not found: {lexicon_path}")
    words = {
        line.strip().split("#", 1)[0].strip()
        for line in lexicon_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    return sorted((word for word in words if len(word) >= 2), key=lambda word: (-len(word), word))


def _pinyin(text: str) -> tuple[str, ...]:
    try:
        from pypinyin import Style, lazy_pinyin
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypinyin is required for domain correction") from exc
    return tuple(lazy_pinyin(text, style=Style.NORMAL, errors=lambda chars: list(chars)))


def pinyin_correct(text: str, lexicon: list[str]) -> tuple[str, list[Correction]]:
    """Replace only equal-length substrings with exactly matching base pinyin.

    The rule is intentionally narrow: it targets homophones while avoiding broad
    fuzzy rewriting. Corpus CER must still decide whether enabling it is useful.
    """

    corrected = text
    changes: list[Correction] = []
    for target in lexicon:
        target_pinyin = _pinyin(target)
        length = len(target)
        index = 0
        while index <= len(corrected) - length:
            before = corrected[index : index + length]
            if before != target and _pinyin(before) == target_pinyin:
                corrected = corrected[:index] + target + corrected[index + length :]
                changes.append(Correction(before, target, index, index + length))
                index += length
            else:
                index += 1
    return corrected, changes

