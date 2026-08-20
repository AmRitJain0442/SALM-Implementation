import textwrap
from salm.importers.markdown_table import parse_markdown


def parse(body):
    return parse_markdown(textwrap.dedent(body))


def test_reads_acronym_and_meaning_from_a_table():
    terms = parse("""
        | Acronyms | Meaning | Notes |
        |---|---|---|
        | AED | Assignment end date | |
        | ASP | Accountable Senior Partner | |
    """)

    assert [(t["canonical"], t["expansion"]) for t in terms] == [
        ("AED", "Assignment end date"),
        ("ASP", "Accountable Senior Partner"),
    ]


def test_skips_the_header_and_separator_rows():
    terms = parse("""
        | Acronyms | Meaning |
        |---|---|
        | AED | Assignment end date |
    """)

    assert len(terms) == 1


def test_keeps_the_notes_column_for_the_reviewer():
    terms = parse("""
        | Acronyms | Meaning | Notes |
        |---|---|---|
        | AP | Associate Partner | They are band 5. |
    """)

    assert terms[0]["note"] == "They are band 5."


def test_flattens_line_break_markup_in_a_cell():
    terms = parse("""
        | Acronyms | Meaning |
        |---|---|
        | ROY | RED (Band 1)<br>ORANGE (Band 2) |
    """)

    assert terms[0]["expansion"] == "RED (Band 1); ORANGE (Band 2)"


def test_drops_a_self_referential_expansion_prefix():
    """'GREEN' meaning 'GREEN (Band 4)' would expand to 'GREEN (GREEN (Band 4))'."""
    terms = parse("""
        | Acronyms | Meaning |
        |---|---|
        | GREEN | GREEN (Band 4) |
    """)

    assert terms[0]["expansion"] == "Band 4"


def test_treats_a_multi_word_entry_as_jargon():
    terms = parse("""
        | Acronyms | Meaning |
        |---|---|
        | EF Recipient | ROYG colleague listed as a feedback recipient |
    """)

    assert terms[0]["type"] == "jargon"
    assert "expansion" not in terms[0]


def test_ignores_a_row_with_no_meaning():
    terms = parse("""
        | Acronyms | Meaning |
        |---|---|
        | XYZ | |
    """)

    assert terms == []


def test_reads_a_table_that_has_no_outer_pipes():
    terms = parse("""
        Acronyms | Meaning
        --- | ---
        AED | Assignment end date
    """)

    assert terms[0]["canonical"] == "AED"


def test_does_not_invent_a_spelled_form_for_a_word_like_term():
    """Nobody says 'G R E E N'. A spelled form is only right for real initialisms."""
    terms = parse("""
        | Acronyms | Meaning |
        |---|---|
        | GREEN | GREEN (Band 4) |
        | ASP | Accountable Senior Partner |
    """)

    green, asp = terms
    assert "spoken_forms" not in green
    assert asp["spoken_forms"] == ["A S P"]


def test_flags_an_expansion_that_would_read_badly_inline():
    """'ROY' meaning three colour bands cannot be dropped into a sentence."""
    terms = parse("""
        | Acronyms | Meaning |
        |---|---|
        | ROY | RED (Band 1)<br>ORANGE (Band 2)<br>YELLOW (Band 3) |
    """)

    assert terms[0]["review"]


def test_a_short_clean_expansion_is_not_flagged():
    terms = parse("""
        | Acronyms | Meaning |
        |---|---|
        | ASP | Accountable Senior Partner |
    """)

    assert "review" not in terms[0]
