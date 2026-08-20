"""The firm's jargon dictionary: the single source of truth for both pipeline stages.

Stage 1 (transcription) needs the *spoken* forms, to bias the ASR decoder.
Stage 2 (expansion) needs the *written* forms and their definitions.
Both come from one file so the two stages can never drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Term:
    canonical: str
    expansion: str | None = None
    type: str = "jargon"
    spoken_forms: tuple[str, ...] = field(default_factory=tuple)
    boost: float | None = None


class Glossary:
    def __init__(self, terms: list[Term]):
        self._terms = terms
        self._by_canonical = {t.canonical: t for t in terms}

    @classmethod
    def load(cls, path: str | Path) -> "Glossary":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        terms: list[Term] = []
        seen: set[str] = set()

        for entry in raw.get("terms", []):
            canonical = entry["canonical"]

            if canonical in seen:
                raise ValueError(
                    f"duplicate term {canonical!r}: each canonical form may appear once"
                )
            seen.add(canonical)

            term = Term(
                canonical=canonical,
                expansion=entry.get("expansion"),
                type=entry.get("type", "jargon"),
                spoken_forms=tuple(entry.get("spoken_forms", ())),
                boost=entry.get("boost"),
            )

            # An acronym with no expansion is almost always an authoring mistake:
            # it would be biased during transcription but silently never expanded.
            if term.type == "acronym" and not term.expansion:
                raise ValueError(f"acronym {canonical!r} has no expansion")

            terms.append(term)

        return cls(terms)

    @property
    def terms(self) -> list[Term]:
        return list(self._terms)

    def lookup(self, canonical: str) -> Term | None:
        return self._by_canonical.get(canonical)

    def biasing_phrases(self) -> list[str]:
        """Every surface form the ASR decoder should be biased toward.

        Includes spoken variants, because an acronym said letter-by-letter
        ("A R R") is acoustically nothing like the written token.
        """
        phrases: list[str] = []
        for term in self._terms:
            for phrase in (term.canonical, *term.spoken_forms):
                if phrase not in phrases:
                    phrases.append(phrase)
        return phrases
