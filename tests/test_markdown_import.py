"""Markdown glossary import.

Fixtures here are invented. Never use a real firm glossary as test data: tests
are committed, and this repository is public.
"""

import textwrap

from salm.importers.markdown_table import parse_markdown


def parse(body):
    return parse_markdown(textwrap.dedent(body))


def test_reads_acronym_and_meaning_from_a_table():
    terms = parse("""
        | Acronym | Meaning | Notes |
        |---|---|---|
        | CRIMS | Client Risk Management System | |
        | QBR | Quarterly Business Review | |
    """)

    assert [(t["canonical"], t["expansion"]) for t in terms] == [
        ("CRIMS", "Client Risk Management System"),
        ("QBR", "Quarterly Business Review"),
    ]


def test_skips_the_header_and_separator_rows():
    terms = parse("""
        | Acronym | Meaning |
        |---|---|
        | CRIMS | Client Risk Management System |
    """)

    assert len(terms) == 1


def test_keeps_the_notes_column_for_the_reviewer():
    terms = parse("""
        | Acronym | Meaning | Notes |
        |---|---|---|
        | QBR | Quarterly Business Review | Runs in the second week. |
    """)

    assert terms[0]["note"] == "Runs in the second week."


def test_flattens_line_break_markup_in_a_cell():
    terms = parse("""
        | Acronym | Meaning |
        |---|---|
        | TIER | GOLD (Level 1)<br>SILVER (Level 2) |
    """)

    assert terms[0]["expansion"] == "GOLD (Level 1); SILVER (Level 2)"


def test_drops_a_self_referential_expansion_prefix():
    """'AMBER' meaning 'AMBER (Level 3)' would expand to 'AMBER (AMBER (Level 3))'."""
    terms = parse("""
        | Acronym | Meaning |
        |---|---|
        | AMBER | AMBER (Level 3) |
    """)

    assert terms[0]["expansion"] == "Level 3"


def test_treats_a_multi_word_entry_as_jargon():
    terms = parse("""
        | Acronym | Meaning |
        |---|---|
        | Nimbus Reviewer | colleague listed as a reviewer on the survey |
    """)

    assert terms[0]["type"] == "jargon"
    assert "expansion" not in terms[0]


def test_ignores_a_row_with_no_meaning():
    terms = parse("""
        | Acronym | Meaning |
        |---|---|
        | XYZ | |
    """)

    assert terms == []


def test_reads_a_table_that_has_no_outer_pipes():
    terms = parse("""
        Acronym | Meaning
        --- | ---
        CRIMS | Client Risk Management System
    """)

    assert terms[0]["canonical"] == "CRIMS"


def test_does_not_invent_a_spelled_form_for_a_word_like_term():
    """Nobody says 'A M B E R'. A spelled form is only right for real initialisms.

    The giveaway is whether the letters match the expansion's initials, not
    whether the term is a dictionary word.
    """
    terms = parse("""
        | Acronym | Meaning |
        |---|---|
        | AMBER | AMBER (Level 3) |
        | QBR | Quarterly Business Review |
    """)

    amber, qbr = terms
    assert "spoken_forms" not in amber
    assert qbr["spoken_forms"] == ["Q B R"]


def test_flags_an_expansion_that_would_read_badly_inline():
    """A meaning that is really a table cannot be dropped into a sentence."""
    terms = parse("""
        | Acronym | Meaning |
        |---|---|
        | TIER | GOLD (Level 1)<br>SILVER (Level 2)<br>BRONZE (Level 3) |
    """)

    assert terms[0]["review"]


def test_a_short_clean_expansion_is_not_flagged():
    terms = parse("""
        | Acronym | Meaning |
        |---|---|
        | QBR | Quarterly Business Review |
    """)

    assert "review" not in terms[0]
