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
