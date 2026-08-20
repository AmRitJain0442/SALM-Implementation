"""Glossary importers.

Every importer produces *candidates* for a human to review rather than writing
the live glossary. Real glossaries contain entries that are wrong for this
system in ways only a person can judge.
"""

from pathlib import Path

import yaml

MARKDOWN = {".md", ".markdown", ".mdown"}
HTML = {".html", ".htm", ".xhtml"}


def parse_file(path: str | Path) -> list[dict]:
    """Read a glossary export, choosing the parser by file type."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in MARKDOWN:
        from .markdown_table import parse_file as parse
    elif suffix in HTML:
        from .confluence import parse_file as parse
    else:
        raise ValueError(
            f"don't know how to read {path.name!r}; "
            f"expected one of {', '.join(sorted(MARKDOWN | HTML))}"
        )
    return parse(path)


def to_yaml(terms: list[dict]) -> str:
    header = (
        "# Candidate glossary entries. REVIEW BEFORE USE.\n"
        "#\n"
        "# A wrong entry here silently corrupts correction for every meeting\n"
        "# afterwards. Two things to check in particular:\n"
        "#\n"
        "#   - Short acronyms (2-3 letters) collide with ordinary speech.\n"
        "#     Delete any you would not want forced into a transcript.\n"
        "#   - `expansion` is what gets written inline on first use. If it\n"
        "#     reads badly in a sentence, shorten it or make the entry jargon.\n"
        "#\n"
        "# Then merge what survives into glossary/terms.yaml.\n\n"
    )
    return header + yaml.safe_dump(
        {"terms": terms}, sort_keys=False, allow_unicode=True, width=88
    )
