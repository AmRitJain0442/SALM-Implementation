"""Stage 2: rewrite recognised acronyms into their full definitions.

Deterministic on purpose. With a small, mostly-unambiguous glossary a lookup
table beats a language model on every axis that matters here: it cannot
hallucinate an expansion, its output is auditable, and it costs no memory that
the ASR model needs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .glossary import Glossary, Term


@dataclass(frozen=True)
class Hit:
    canonical: str
    expansion: str


@dataclass(frozen=True)
class Result:
    text: str
    hits: tuple[Hit, ...]


class Expander:
    """Expands acronyms, tracking what has already been expanded this session.

    Policy `first_use` expands a term the first time it is heard and leaves
    later mentions bare, which keeps a long transcript readable.
    """

    def __init__(self, glossary: Glossary, policy: str = "first_use"):
        if policy not in ("first_use", "always", "never"):
            raise ValueError(f"unknown expansion policy {policy!r}")
        self._glossary = glossary
        self._policy = policy
        self._seen: set[str] = set()
        self._pattern = self._build_pattern(glossary)

    @staticmethod
    def _build_pattern(glossary: Glossary) -> re.Pattern | None:
        expandable = [t for t in glossary.terms if t.expansion]
        if not expandable:
            return None
        # Longest first so a multi-word term wins over a shorter term nested
        # inside it; \b stops ARR from matching inside BARRIER.
        forms = sorted((t.canonical for t in expandable), key=len, reverse=True)
        return re.compile(r"\b(" + "|".join(re.escape(f) for f in forms) + r")\b")

    def reset(self) -> None:
        """Forget what has been expanded. Call when a new session starts."""
        self._seen.clear()

    def expand(self, text: str) -> Result:
        if self._pattern is None or self._policy == "never":
            return Result(text=text, hits=())

        hits: list[Hit] = []

        def replace(match: re.Match) -> str:
            canonical = match.group(1)
            term: Term = self._glossary.lookup(canonical)
            if term is None or not term.expansion:
                return canonical
            if self._policy == "first_use" and canonical in self._seen:
                return canonical
            self._seen.add(canonical)
            hits.append(Hit(canonical=canonical, expansion=term.expansion))
            return f"{canonical} ({term.expansion})"

        return Result(text=self._pattern.sub(replace, text), hits=tuple(hits))
