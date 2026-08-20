"""Repair jargon the recogniser almost got right.

Measurement showed the ASR model's residual jargon errors are near-misses
("Halbert" for "Halberd", "Orbeck's" for "Orbex") rather than wild guesses, so
a similarity match against the small glossary recovers them. Contextual biasing
was tried first and measured worse on every axis; see MEMORY.md.

The dominant risk here is over-correction: turning ordinary English into
jargon is far more damaging than leaving a term misspelled, so the matcher is
deliberately conservative.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from .glossary import Glossary

def _load_common_words() -> frozenset[str]:
    """The most frequent English words, used to refuse over-correction.

    If the recogniser produced a word this common, it is far more likely to be
    what the speaker actually said than a mangled glossary term. Measured
    against 350k English words, this guard removes the false corrections that
    matter -- "crimes" scores 0.91 against CRIMS and would otherwise be
    rewritten in any compliance meeting.

    Frequency, not dictionary membership, is the right test: a full dictionary
    also contains "halbert", and that *is* a near-miss the corrector should fix.
    """
    path = Path(__file__).resolve().parent / "data" / "common_words.txt"
    if not path.exists():
        return frozenset()
    return frozenset(
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )


COMMON_WORDS = _load_common_words()

# A word, optionally with a possessive tail the recogniser tacked on.
_WORD = re.compile(r"[A-Za-z][A-Za-z]*(?:'s|'S)?")

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


def _is_longer_word_containing(heard: str, term: str) -> bool:
    """True when the heard word is a real word that merely contains the term.

    Similarity scoring rewards a shared prefix heavily, so a short acronym gets
    a high score against any longer word starting with it -- "crimson" scores
    0.83 against "CRIMS". Losing an ordinary word to a false correction is worse
    than leaving a term uncorrected, so these are refused.

    One or two extra characters is still treated as a plausible recognition
    error ("Skylar" for "Skylark"), not a different word.
    """
    if len(heard) <= len(term) + 1:
        return False
    return heard.startswith(term) or heard.endswith(term)


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

        terms = [t.canonical for t in glossary.terms]
        self._exact = {t.lower() for t in terms}
        self._soundex = {t: soundex(t) for t in terms}

        # Grouped by word count so an n-word window is only compared against
        # terms of the same length.
        self._by_length: dict[int, list[str]] = {}
        for term in terms:
            self._by_length.setdefault(len(term.split()), []).append(term)
        self._longest = max(self._by_length, default=1)

    def _strip_possessive(self, phrase: str) -> str:
        return phrase[:-2] if phrase.lower().endswith("'s") else phrase

    def _best_match(self, phrase: str, length: int) -> tuple[str, float] | None:
        candidates = self._by_length.get(length)
        if not candidates:
            return None

        stem = self._strip_possessive(phrase)
        lowered = stem.lower()

        if lowered in self._exact:
            return None
        # Ordinary English is never jargon, however similar it looks. For a
        # multi-word window, only reject when every word is ordinary.
        if all(w.lower() in COMMON_WORDS for w in stem.split()):
            return None

        best, best_score = None, 0.0
        for term in candidates:
            score = difflib.SequenceMatcher(None, lowered, term.lower()).ratio()
            if score > best_score:
                best, best_score = term, score
        if best is None:
            return None

        if _is_longer_word_containing(lowered, best.lower()):
            return None

        # Accept either a strong spelling match, or a weaker one that also
        # sounds alike -- the signature of a phonetic misrecognition.
        sounds_alike = soundex(stem.replace(" ", "")) == soundex(best.replace(" ", ""))
        floor = self._phonetic_threshold if sounds_alike else self._threshold
        if best_score < floor:
            return None
        return best, best_score

    def correct(self, text: str) -> Result:
        words = list(_WORD.finditer(text))
        hits: list[Correction] = []
        pieces: list[str] = []
        cursor = 0   # index into `text`
        i = 0        # index into `words`

        while i < len(words):
            longest = min(self._longest, len(words) - i)
            for length in range(longest, 0, -1):
                start = words[i].start()
                end = words[i + length - 1].end()
                phrase = text[start:end]

                # A window must be plain words separated by single spaces;
                # punctuation between them means they are not one phrase.
                if length > 1 and not re.fullmatch(r"[A-Za-z' ]+", phrase):
                    continue

                found = self._best_match(phrase, length)
                if found is None:
                    continue

                canonical, score = found
                pieces.append(text[cursor:start])
                pieces.append(canonical)
                hits.append(Correction(heard=phrase, canonical=canonical, score=score))
                cursor = end
                i += length
                break
            else:
                i += 1

        pieces.append(text[cursor:])
        return Result(text="".join(pieces), hits=tuple(hits))
