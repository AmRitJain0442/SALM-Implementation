import textwrap
from salm.importers.confluence import parse_html


def test_reads_a_two_column_table_as_term_and_definition():
    html = """<table><tbody>
      <tr><th>Term</th><th>Definition</th></tr>
      <tr><td>ARR</td><td>Annual Recurring Revenue</td></tr>
      <tr><td>CRIMS</td><td>Client Risk Management System</td></tr>
    </tbody></table>"""

    terms = parse_html(html)

    assert [(t["canonical"], t["expansion"]) for t in terms] == [
        ("ARR", "Annual Recurring Revenue"),
        ("CRIMS", "Client Risk Management System"),
    ]


def test_classifies_an_all_caps_short_entry_as_an_acronym():
    html = "<table><tr><td>ARR</td><td>Annual Recurring Revenue</td></tr></table>"

    assert parse_html(html)[0]["type"] == "acronym"


def test_classifies_a_normal_word_as_jargon():
    html = "<table><tr><td>Halberd</td><td>the overnight batch</td></tr></table>"

    assert parse_html(html)[0]["type"] == "jargon"


def test_skips_the_header_row():
    html = "<table><tr><th>Term</th><th>Meaning</th></tr></table>"

    assert parse_html(html) == []


def test_reads_definition_list_markup():
    html = "<dl><dt>Skylark</dt><dd>the trading platform</dd></dl>"

    terms = parse_html(html)

    assert terms[0]["canonical"] == "Skylark"


def test_a_jargon_definition_is_a_note_not_an_expansion():
    """Only acronyms get expanded in transcripts; jargon just needs spelling."""
    html = "<dl><dt>Skylark</dt><dd>the trading platform</dd></dl>"

    term = parse_html(html)[0]

    assert term["note"] == "the trading platform"
    assert "expansion" not in term


def test_ignores_rows_without_a_definition():
    html = "<table><tr><td>Orphan</td></tr></table>"

    assert parse_html(html) == []


def test_strips_nested_markup_and_entities():
    html = "<table><tr><td><strong>ARR</strong></td><td>Annual &amp; Recurring</td></tr></table>"

    terms = parse_html(html)

    assert terms[0]["canonical"] == "ARR"
    assert terms[0]["expansion"] == "Annual & Recurring"
