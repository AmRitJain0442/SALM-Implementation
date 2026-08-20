"""Composes the stages into the transformation applied to one utterance.

Kept separate from transport (websockets, microphones) so the whole
text path can be tested without audio hardware or a running server.
"""

from __future__ import annotations

from dataclasses import dataclass

from .asr import is_filler
from .correct import Correction, Corrector
from .expand import Hit
from .expand import Expander
from .glossary import Glossary


@dataclass(frozen=True)
class Utterance:
    raw: str
    text: str
    corrections: tuple[Correction, ...]
    expansions: tuple[Hit, ...]


class Pipeline:
    def __init__(
        self,
        glossary: Glossary,
        threshold: float = 0.75,
        policy: str = "first_use",
    ):
        self._corrector = Corrector(glossary, threshold=threshold)
        self._expander = Expander(glossary, policy=policy)

    def reset(self) -> None:
        """Start a new session: acronyms expand on first use again."""
        self._expander.reset()

    def process(self, raw: str) -> Utterance | None:
        """Correct then expand one utterance, or None if it carries no meaning.

        Correction runs first so that expansion sees canonical spellings --
        an acronym misheard as "Crims" must be repaired before it can be
        looked up.
        """
        if is_filler(raw):
            return None

        corrected = self._corrector.correct(raw)
        expanded = self._expander.expand(corrected.text)

        return Utterance(
            raw=raw,
            text=expanded.text,
            corrections=corrected.hits,
            expansions=expanded.hits,
        )
