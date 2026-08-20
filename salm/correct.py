"""Repair jargon the recogniser almost got right.

Measurement showed the ASR model's residual jargon errors are near-misses
("Halbert" for "Halberd", "Orbeck's" for "Orbex") rather than wild guesses, so
a similarity match against the small glossary recovers them. Contextual biasing
was tried first and measured worse on every axis; see the design doc.

The dominant risk here is over-correction: turning ordinary English into
jargon is far more damaging than leaving a term misspelled, so the matcher is
deliberately conservative.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from .glossary import Glossary

# Words that must never be "corrected" into jargon, however similar they look.
# Short, ordinary English carries most of the false-positive risk.
COMMON_WORDS = {
    "a", "about", "after", "again", "all", "already", "also", "and", "another",
    "any", "are", "around", "as", "at", "back", "batch", "be", "because",
    "been", "before", "being", "below", "between", "both", "but", "by", "call",
    "can", "come", "could", "day", "did", "do", "does", "done", "down", "each",
    "even", "every", "few", "first", "for", "from", "get", "give", "go", "good",
    "great", "had", "has", "have", "he", "her", "here", "him", "his", "how",
    "if", "in", "into", "is", "it", "its", "just", "know", "last", "least",
    "left", "less", "let", "like", "little", "long", "look", "made", "make",
    "many", "may", "me", "might", "monday", "more", "morning", "most", "much",
    "must", "my", "need", "never", "new", "next", "night", "no", "not", "now",
    "number", "of", "off", "on", "once", "one", "only", "onto", "or", "other",
    "our", "out", "over", "own", "part", "patch", "people", "per", "place",
    "point", "put", "quarter", "quarterly", "report", "right", "run", "runs",
    "said", "same", "say", "see", "she", "should", "since", "so", "some",
    "still", "such", "take", "than", "that", "the", "their", "them", "then",
    "there", "these", "they", "thing", "think", "this", "those", "three",
    "through", "time", "to", "today", "too", "trade", "trades", "two", "under",
    "up", "us", "use", "used", "very", "want", "was", "way", "we", "week",
    "well", "were", "what", "when", "where", "which", "while", "who", "why",
    "will", "with", "work", "would", "year", "yes", "yet", "you", "your",
}

# A word, optionally with a possessive/plural tail the recogniser tacked on.
_WORD = re.compile(r"\b[A-Za-z][A-Za-z]*(?:'s|'S)?\b")

_SOUNDEX_CODES = {
    **{c: "1" for c in "bfpv"}, **{c: "2" for c in "cgjkqsxz"},
    **{c: "3" for c in "dt"}, "l": "4", **{c: "5" for c in "mn"}, "r": "6",
}


def soundex(word: str) -> str:
    """Classic Soundex key. Two words sharing a key sound alike.

    ASR errors are phonetic confusions, so a shared key is strong evidence
    that a misrecognised word is really a glossary term.
    """
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return ""
    first = word[0]
    prev = _SOUNDEX_CODES.get(first, "")
    digits = []
    for char in word[1:]:
        code = _SOUNDEX_CODES.get(char, "")
        if code and code != prev:
            digits.append(code)
        # Vowels break a run of same-coded letters; h and w are transparent.
        if char not in "hw":
            prev = code
    return (first.upper() + "".join(digits) + "000")[:4]



@dataclass(frozen=True)
class Correction:
    heard: str
    canonical: str
    score: float


@dataclass(frozen=True)
class Result:
    text: str
    hits: tuple[Correction, ...]


class Corrector:
    def __init__(
        self,
        glossary: Glossary,
        threshold: float = 0.75,
        phonetic_threshold: float = 0.6,
    ):
        self._threshold = threshold
        self._phonetic_threshold = phonetic_threshold
        self._terms = [t.canonical for t in glossary.terms]
        self._exact = {t.lower() for t in self._terms}
        self._soundex = {t: soundex(t) for t in self._terms}

    def _best_match(self, word: str) -> tuple[str, float] | None:
        stem = word[:-2] if word.lower().endswith("'s") else word
        lowered = stem.lower()

        if lowered in self._exact or lowered in COMMON_WORDS:
            return None

        best, best_score = None, 0.0
        for term in self._terms:
            score = difflib.SequenceMatcher(None, lowered, term.lower()).ratio()
            if score > best_score:
                best, best_score = term, score

        if best is None:
            return None

        # Accept either a strong spelling match, or a weaker one that also
        # sounds alike -- the signature of a phonetic misrecognition.
        sounds_alike = soundex(stem) == self._soundex[best]
        floor = self._phonetic_threshold if sounds_alike else self._threshold
        if best_score < floor:
            return None
        return best, best_score

    def correct(self, text: str) -> Result:
        hits: list[Correction] = []

        def replace(match: re.Match) -> str:
            word = match.group(0)
            found = self._best_match(word)
            if found is None:
                return word
            canonical, score = found
            hits.append(Correction(heard=word, canonical=canonical, score=score))
            return canonical

        return Result(text=_WORD.sub(replace, text), hits=tuple(hits))
