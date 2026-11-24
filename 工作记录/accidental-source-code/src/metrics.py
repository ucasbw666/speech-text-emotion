"""Character-level ASR metrics with explicit edit-operation counts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .text_normalization import normalize_text


@dataclass(frozen=True)
class EditCounts:
    substitutions: int = 0
    deletions: int = 0
    insertions: int = 0
    reference_characters: int = 0

    @property
    def errors(self) -> int:
        return self.substitutions + self.deletions + self.insertions

    @property
    def cer(self) -> float:
        if self.reference_characters == 0:
            return 0.0 if self.errors == 0 else float(self.errors)
        return self.errors / self.reference_characters

    def to_dict(self) -> dict[str, int | float]:
        return {**asdict(self), "errors": self.errors, "cer": self.cer}


@dataclass(frozen=True)
class _Cell:
    cost: int
    substitutions: int
    deletions: int
    insertions: int
    priority: int = 0


def levenshtein_counts(reference: str, hypothesis: str, *, normalize: bool = True) -> EditCounts:
    """Return deterministic Levenshtein S/D/I counts at character level."""

    if normalize:
        reference = normalize_text(reference)
        hypothesis = normalize_text(hypothesis)
    ref = list(reference)
    hyp = list(hypothesis)

    previous = [_Cell(j, 0, 0, j, 3) for j in range(len(hyp) + 1)]
    for i, ref_char in enumerate(ref, start=1):
        current = [_Cell(i, 0, i, 0, 2)]
        for j, hyp_char in enumerate(hyp, start=1):
            diagonal = previous[j - 1]
            if ref_char == hyp_char:
                candidates = [_Cell(
                    diagonal.cost,
                    diagonal.substitutions,
                    diagonal.deletions,
                    diagonal.insertions,
                    0,
                )]
            else:
                candidates = [_Cell(
                    diagonal.cost + 1,
                    diagonal.substitutions + 1,
                    diagonal.deletions,
                    diagonal.insertions,
                    1,
                )]

            deletion = previous[j]
            candidates.append(_Cell(
                deletion.cost + 1,
                deletion.substitutions,
                deletion.deletions + 1,
                deletion.insertions,
                2,
            ))
            insertion = current[j - 1]
            candidates.append(_Cell(
                insertion.cost + 1,
                insertion.substitutions,
                insertion.deletions,
                insertion.insertions + 1,
                3,
            ))
            current.append(min(candidates, key=lambda cell: (cell.cost, cell.priority)))
        previous = current

    result = previous[-1]
    return EditCounts(
        substitutions=result.substitutions,
        deletions=result.deletions,
        insertions=result.insertions,
        reference_characters=len(ref),
    )


def corpus_cer(pairs: Iterable[tuple[str, str]], *, normalize: bool = True) -> EditCounts:
    substitutions = deletions = insertions = reference_characters = 0
    for reference, hypothesis in pairs:
        counts = levenshtein_counts(reference, hypothesis, normalize=normalize)
        substitutions += counts.substitutions
        deletions += counts.deletions
        insertions += counts.insertions
        reference_characters += counts.reference_characters
    return EditCounts(substitutions, deletions, insertions, reference_characters)


def cer(reference: str, hypothesis: str, *, normalize: bool = True) -> float:
    return levenshtein_counts(reference, hypothesis, normalize=normalize).cer

