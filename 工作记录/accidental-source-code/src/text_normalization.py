"""Shared text normalization for training, decoding and CER evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class NormalizationConfig:
    """Options that must stay identical across data splits and evaluation."""

    lowercase_english: bool = True
    remove_punctuation: bool = True
    remove_symbols: bool = True
    remove_whitespace: bool = True
    normalize_width: bool = True


DEFAULT_CONFIG = NormalizationConfig()


def normalize_text(text: str | None, config: NormalizationConfig = DEFAULT_CONFIG) -> str:
    """Normalize Chinese ASR text without changing the lexical content.

    NFKC unifies full-width/half-width forms. Punctuation and decorative symbols
    are removed by Unicode category rather than by a language-specific short list.
    Digits are intentionally retained; spoken-number conversion is dataset-specific.
    """

    if text is None:
        return ""
    normalized = str(text).strip()
    if config.normalize_width:
        normalized = unicodedata.normalize("NFKC", normalized)
    if config.lowercase_english:
        normalized = normalized.lower()

    kept: list[str] = []
    for char in normalized:
        category = unicodedata.category(char)
        if config.remove_punctuation and category.startswith("P"):
            continue
        if config.remove_symbols and category.startswith("S"):
            continue
        kept.append(char)
    normalized = "".join(kept)

    if config.remove_whitespace:
        normalized = _WHITESPACE_RE.sub("", normalized)
    else:
        normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def normalize_batch(texts: list[str], config: NormalizationConfig = DEFAULT_CONFIG) -> list[str]:
    return [normalize_text(text, config) for text in texts]

