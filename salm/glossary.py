"""The firm's jargon dictionary: the single source of truth for both stages.

Stage 1 (transcription) needs the *spoken* forms, to bias the ASR decoder.
Stage 2 (correction and expansion) needs the *written* forms and definitions.
Both come from one file so the two stages can never drift apart.

Loading is strict on purpose. A misspelled field silently does nothing, and a
glossary that quietly ignores half its entries corrupts every meeting
afterwards without anyone noticing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

TYPES = {"acronym", "jargon"}
FIELDS = {"canonical", "expansion", "type", "spoken_forms", "boost", "note"}


@dataclass(frozen=True)
class Term:
    canonical: str
    expansion: str | None = None
    type: str = "jargon"
    spoken_forms: tuple[str, ...] = field(default_factory=tuple)
    boost: float | None = None
    note: str | None = None


class Glossary:
    def __init__(self, terms: list[Term]):
        self._terms = terms
        self._by_canonical = {t.canonical: t for t in terms}

    @classmethod
    def load(cls, path: str | Path) -> "Glossary":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        terms: list[Term] = []
        seen: set[str] = set()

        for index, entry in enumerate(raw.get("terms", [])):
            where = f"entry {index + 1}"

            if not isinstance(entry, dict) or "canonical" not in entry:
                raise ValueError(f"{where}: every term needs a 'canonical' form")

            canonical = entry["canonical"]
            where = f"term {canonical!r}"

            unknown = set(entry) - FIELDS
            if unknown:
                raise ValueError(
                    f"{where}: unknown field(s) {', '.join(sorted(unknown))}; "
                    f"expected one of {', '.join(sorted(FIELDS))}"
                )

            kind = entry.get("type", "jargon")
            if kind not in TYPES:
                raise ValueError(
                    f"{where}: unknown type {kind!r}; expected acronym or jargon"
                )

            if canonical in seen:
                raise ValueError(f"{where}: duplicate; each canonical form may appear once")
            seen.add(canonical)

            term = Term(
                canonical=canonical,
                expansion=entry.get("expansion"),
                type=kind,
                spoken_forms=tuple(entry.get("spoken_forms", ())),
                boost=entry.get("boost"),
                note=entry.get("note"),
            )

            # An acronym with no expansion is almost always an authoring
            # mistake: it would be corrected but silently never expanded.
            if term.type == "acronym" and not term.expansion:
                raise ValueError(f"{where}: acronym has no expansion")

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
