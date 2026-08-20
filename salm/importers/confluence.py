"""Turn a Confluence glossary export into candidate glossary entries.

This deliberately produces a *candidate* file for a human to review rather than
writing glossary/terms.yaml directly. Exported pages are messy, and a bad entry
here is not harmless: a wrong term silently corrupts correction for every
meeting afterwards.

Uses the standard library's HTML parser so importing a glossary pulls in no
new dependency.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import yaml

# Column headings that mean "this row is a heading, not a term".
_HEADINGS = {"term", "terms", "acronym", "acronyms", "abbreviation", "name",
             "definition", "meaning", "description", "expansion", "stands for"}


class _Collector(HTMLParser):
    """Collects table rows and definition lists as (left, right) text pairs."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pairs: list[tuple[str, str]] = []
        self._cells: list[str] = []
        self._buffer: list[str] = []
        self._capturing = False
        self._pending_term: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th", "dt", "dd"):
            self._capturing = True
            self._buffer = []
        elif tag == "tr":
            self._cells = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._cells.append(self._text())
            self._capturing = False
        elif tag == "dt":
            self._pending_term = self._text()
            self._capturing = False
        elif tag == "dd":
            if self._pending_term:
                self.pairs.append((self._pending_term, self._text()))
                self._pending_term = None
            self._capturing = False
        elif tag == "tr":
            if len(self._cells) >= 2:
                self.pairs.append((self._cells[0], self._cells[1]))
            self._cells = []

    def handle_data(self, data):
        if self._capturing:
            self._buffer.append(data)

    def _text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._buffer)).strip()


def _classify(canonical: str) -> str:
    """Acronyms are short and all-caps; everything else is jargon."""
    letters = re.sub(r"[^A-Za-z]", "", canonical)
    if 2 <= len(letters) <= 8 and letters.isupper():
        return "acronym"
    return "jargon"


def parse_html(html: str) -> list[dict]:
    collector = _Collector()
    collector.feed(html)

    terms: list[dict] = []
    seen: set[str] = set()

    for left, right in collector.pairs:
        canonical, expansion = left.strip(), right.strip()
        if not canonical or not expansion:
            continue
        if canonical.lower() in _HEADINGS or expansion.lower() in _HEADINGS:
            continue
        if canonical.lower() in seen:
            continue
        seen.add(canonical.lower())

        entry: dict = {"canonical": canonical, "type": _classify(canonical)}
        if entry["type"] == "acronym":
            entry["expansion"] = expansion
            # Acronyms are usually said letter by letter; record that so the
            # optional biasing path has the right spoken form.
            entry["spoken_forms"] = [" ".join(re.sub(r"[^A-Za-z]", "", canonical))]
        else:
            # Jargon needs correct spelling, not expansion -- rewriting every
            # mention of a product name with its definition makes transcripts
            # unreadable. The definition is kept for whoever reviews the import.
            entry["note"] = expansion
        terms.append(entry)

    return terms


def parse_file(path: str | Path) -> list[dict]:
    return parse_html(Path(path).read_text(encoding="utf-8", errors="replace"))


def to_yaml(terms: list[dict]) -> str:
    header = (
        "# Candidate glossary entries imported from a Confluence export.\n"
        "# REVIEW BEFORE USE: a wrong entry here silently corrupts correction\n"
        "# for every meeting afterwards. Delete what does not belong, then\n"
        "# merge into glossary/terms.yaml.\n\n"
    )
    return header + yaml.safe_dump(
        {"terms": terms}, sort_keys=False, allow_unicode=True, width=88
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Confluence export -> candidate glossary")
    parser.add_argument("export", help="exported .html page")
    parser.add_argument("-o", "--out", default="glossary/candidates.yaml")
    args = parser.parse_args()

    terms = parse_file(args.export)
    Path(args.out).write_text(to_yaml(terms), encoding="utf-8")

    acronyms = sum(1 for t in terms if t["type"] == "acronym")
    print(f"{len(terms)} candidates ({acronyms} acronyms) -> {args.out}")
    print("Review before merging into glossary/terms.yaml.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
