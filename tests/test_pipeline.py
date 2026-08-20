from salm.glossary import Glossary, Term
from salm.pipeline import Pipeline


def build():
    g = Glossary([
        Term(canonical="Halberd", type="jargon"),
        Term(canonical="CRIMS", expansion="Client Risk Management System", type="acronym"),
    ])
    return Pipeline(glossary=g)


def test_corrects_then_expands_in_one_pass():
    result = build().process("Halbert feeds CRIMS nightly")

    assert result.text == "Halberd feeds CRIMS (Client Risk Management System) nightly"


def test_drops_hallucinated_filler():
    assert build().process("Okay.") is None


def test_drops_empty_text():
    assert build().process("   ") is None


def test_reports_corrections_and_expansions_separately():
    result = build().process("Halbert feeds CRIMS nightly")

    assert [c.canonical for c in result.corrections] == ["Halberd"]
    assert [e.canonical for e in result.expansions] == ["CRIMS"]
