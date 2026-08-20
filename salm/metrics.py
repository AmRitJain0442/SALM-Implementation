"""Measurement for the evaluation harness.

Two numbers decide whether this system works:

  term recall  -- did the firm's jargon come out spelled correctly?
  word error rate -- did the rest of the sentence survive intact?

Recall alone is not enough. Any aggressive term-forcing scheme can raise recall
while wrecking ordinary speech, which is exactly what contextual biasing did
here. WER is the guardrail that catches it.
"""

from __future__ import annotations

import re


def normalize(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", text.lower()).split()


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Levenshtein distance over words, divided by reference length."""
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0

    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        current = [i]
        for j, h in enumerate(hyp, start=1):
            current.append(min(
                previous[j] + 1,            # deletion
                current[j - 1] + 1,         # insertion
                previous[j - 1] + (r != h),  # substitution
            ))
        previous = current
    return previous[-1] / len(ref)


def term_recall(terms: list[str], hypothesis: str) -> tuple[int, int]:
    """How many of the expected terms appear as whole words in the output."""
    found = sum(
        1 for term in terms
        if re.search(rf"\b{re.escape(term)}\b", hypothesis, flags=re.IGNORECASE)
    )
    return found, len(terms)
