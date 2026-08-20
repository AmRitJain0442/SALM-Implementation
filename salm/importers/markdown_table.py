"""Read glossary entries out of a Markdown table.

Wiki exports are as often Markdown as HTML. The shape assumed here is the one
glossaries actually take: term in the first column, meaning in the second, and
optional commentary after that.

Like the HTML importer, this produces *candidates* for a human to review. Real
glossaries carry entries that are wrong for this system in ways only a person
can judge -- a two-letter acronym that collides with ordinary speech, or a
"meaning" that is really a note.
"""

from __future__ import annotations

import re
from pathlib import Path

# Column headings, so a header row is not imported as a term.
_HEADINGS = {
    "acronym", "acronyms", "term", "terms", "abbreviation", "abbreviations",
    "name", "meaning", "definition", "description", "expansion", "notes",
    "note", "stands for", "role responsibility", "responsibility",
}

_SEPARATOR = re.compile(r"^[\s|:-]+$")


def _cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _clean(cell: str) -> str:
    """Flatten inline markup a wiki export leaves behind."""
    cell = re.sub(r"<\s*br\s*/?\s*>", "; ", cell, flags=re.I)
    cell = re.sub(r"<[^>]+>", "", cell)          # any other stray tags
    cell = cell.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", cell).strip(" ;")


def classify(canonical: str) -> str:
    """Acronyms are short, single tokens, and written in capitals."""
    if " " in canonical.strip():
        return "jargon"
    letters = re.sub(r"[^A-Za-z]", "", canonical)
    if 2 <= len(letters) <= 8 and letters.isupper():
        return "acronym"
    return "jargon"


def _is_spelled_out(canonical: str, expansion: str) -> bool:
    """Whether people read this term letter by letter.

    A true initialism has letters that match the initials of what it stands
    for: ASP for "Accountable Senior Partner". A label that happens to be
    written in capitals does not -- GREEN means "Band 4", and nobody says
    "G R E E N".

    Being an ordinary English word is not the test: "asp" is in the dictionary,
    but ASP here is still spelled out.
    """
    letters = re.sub(r"[^A-Za-z]", "", canonical).lower()
    initials = "".join(w[0] for w in re.findall(r"[A-Za-z]+", expansion)).lower()
    return bool(letters) and initials.startswith(letters)


def _reads_badly_inline(expansion: str) -> bool:
    """Whether dropping this into a sentence would produce something unreadable.

    Expansions are written inline on first use, so a meaning that is really a
    table of values needs a human to shorten it before it is usable.
    """
    return (
        len(expansion) > 60
        or ";" in expansion
        or expansion.count("(") > 1
    )


def _strip_self_reference(canonical: str, expansion: str) -> str:
    """Remove a leading repeat of the term from its own meaning.

    A row like `GREEN | GREEN (Band 4)` would otherwise expand in transcripts
    to "GREEN (GREEN (Band 4))".
    """
    if expansion.upper().startswith(canonical.upper()):
        trimmed = expansion[len(canonical):].strip(" :-–—")
        if trimmed.startswith("(") and trimmed.endswith(")"):
            trimmed = trimmed[1:-1].strip()
        if trimmed:
            return trimmed
    return expansion


def parse_markdown(text: str) -> list[dict]:
    terms: list[dict] = []
    seen: set[str] = set()

    for line in text.splitlines():
        if "|" not in line or _SEPARATOR.match(line):
            continue

        cells = _cells(line)
        if len(cells) < 2:
            continue

        canonical = _clean(cells[0])
        expansion = _clean(cells[1])
        note = " ".join(_clean(c) for c in cells[2:] if _clean(c))

        if not canonical or not expansion:
            continue
        if canonical.lower() in _HEADINGS or expansion.lower() in _HEADINGS:
            continue
        if canonical.lower() in seen:
            continue
        seen.add(canonical.lower())

        entry: dict = {"canonical": canonical, "type": classify(canonical)}

        if entry["type"] == "acronym":
            entry["expansion"] = _strip_self_reference(canonical, expansion)
            if _is_spelled_out(canonical, entry["expansion"]):
                entry["spoken_forms"] = [" ".join(re.sub(r"[^A-Za-z]", "", canonical))]
            if _reads_badly_inline(entry["expansion"]):
                entry["review"] = "expansion is long or structured; shorten it"
        else:
            # Jargon is corrected for spelling, never expanded inline -- see
            # the HTML importer for why.
            note = f"{expansion} {note}".strip()

        if note:
            entry["note"] = note
        terms.append(entry)

    return terms


def parse_file(path: str | Path) -> list[dict]:
    return parse_markdown(Path(path).read_text(encoding="utf-8", errors="replace"))
