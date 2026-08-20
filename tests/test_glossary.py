import textwrap
import pytest
from salm.glossary import Glossary


def write(tmp_path, body):
    p = tmp_path / "terms.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_loads_an_acronym_with_its_expansion(tmp_path):
    path = write(tmp_path, """
        terms:
          - canonical: ARR
            expansion: Annual Recurring Revenue
            type: acronym
    """)

    glossary = Glossary.load(path)

    term = glossary.lookup("ARR")
    assert term.canonical == "ARR"
    assert term.expansion == "Annual Recurring Revenue"


def test_rejects_an_acronym_that_has_no_expansion(tmp_path):
    path = write(tmp_path, """
        terms:
          - canonical: ARR
            type: acronym
    """)

    with pytest.raises(ValueError, match="ARR"):
        Glossary.load(path)


def test_rejects_duplicate_canonical_terms(tmp_path):
    path = write(tmp_path, """
        terms:
          - canonical: ARR
            expansion: Annual Recurring Revenue
            type: acronym
          - canonical: ARR
            expansion: Accounting Rate of Return
            type: acronym
    """)

    with pytest.raises(ValueError, match="ARR"):
        Glossary.load(path)


def test_biasing_phrases_include_canonical_and_spoken_forms(tmp_path):
    path = write(tmp_path, """
        terms:
          - canonical: ARR
            expansion: Annual Recurring Revenue
            type: acronym
            spoken_forms: ["A R R"]
          - canonical: Kubernetes
            type: jargon
    """)

    phrases = Glossary.load(path).biasing_phrases()

    assert "ARR" in phrases
    assert "A R R" in phrases
    assert "Kubernetes" in phrases


def test_rejects_an_unknown_field_that_is_probably_a_typo(tmp_path):
    path = write(tmp_path, """
        terms:
          - canonical: ARR
            expansionn: Annual Recurring Revenue
            type: acronym
    """)

    with pytest.raises(ValueError, match="expansionn"):
        Glossary.load(path)


def test_rejects_an_unknown_term_type(tmp_path):
    path = write(tmp_path, """
        terms:
          - canonical: Skylark
            type: jargonn
    """)

    with pytest.raises(ValueError, match="jargonn"):
        Glossary.load(path)


def test_rejects_a_term_with_no_canonical_form(tmp_path):
    path = write(tmp_path, """
        terms:
          - expansion: Annual Recurring Revenue
            type: acronym
    """)

    with pytest.raises(ValueError, match="canonical"):
        Glossary.load(path)


def test_accepts_a_note_on_a_jargon_term(tmp_path):
    """The Confluence importer records definitions for jargon as notes."""
    path = write(tmp_path, """
        terms:
          - canonical: Skylark
            type: jargon
            note: the trading platform
    """)

    assert Glossary.load(path).lookup("Skylark").note == "the trading platform"


def test_reports_which_entry_was_wrong(tmp_path):
    path = write(tmp_path, """
        terms:
          - canonical: ARR
            expansion: Annual Recurring Revenue
            type: acronym
          - canonical: Skylark
            type: jargonn
    """)

    with pytest.raises(ValueError, match="Skylark"):
        Glossary.load(path)
