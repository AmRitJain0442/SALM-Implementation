import pytest
from salm.glossary import Glossary, Term
from salm.correct import Corrector


def glossary(*names):
    return Glossary([Term(canonical=n, type="jargon") for n in names])


def test_corrects_a_near_miss_to_the_glossary_term():
    corrector = Corrector(glossary("Halberd"))

    result = corrector.correct("feeds Halbert every morning")

    assert result.text == "feeds Halberd every morning"


def test_corrects_across_a_possessive_ending():
    corrector = Corrector(glossary("Orbex"))

    result = corrector.correct("Orbeck's reconciliation runs")

    assert result.text.startswith("Orbex")


def test_leaves_an_exact_match_untouched():
    corrector = Corrector(glossary("Nimbus"))

    result = corrector.correct("in the Nimbus tier")

    assert result.text == "in the Nimbus tier"
    assert result.hits == ()


def test_does_not_corrupt_an_ordinary_english_word():
    # 'number' is close to 'Nimbus' but is plainly not the jargon term.
    corrector = Corrector(glossary("Nimbus"))

    result = corrector.correct("the number of trades")

    assert result.text == "the number of trades"


def test_does_not_invent_a_term_from_an_unrelated_word():
    corrector = Corrector(glossary("Quantex"))

    result = corrector.correct("the quarterly report")

    assert result.text == "the quarterly report"


def test_reports_what_it_changed():
    corrector = Corrector(glossary("Halberd"))

    result = corrector.correct("feeds Halbert today")

    assert [(h.heard, h.canonical) for h in result.hits] == [("Halbert", "Halberd")]


def test_preserves_surrounding_punctuation():
    corrector = Corrector(glossary("Skylark"))

    result = corrector.correct("onto Skylarc, then done.")

    assert result.text == "onto Skylark, then done."


def test_corrects_a_multi_word_term():
    corrector = Corrector(glossary("Nimbus Tier"))

    result = corrector.correct("the Nimbus Teer held up")

    assert result.text == "the Nimbus Tier held up"


def test_prefers_the_longer_term_when_both_could_match():
    corrector = Corrector(glossary("Nimbus", "Nimbus Tier"))

    result = corrector.correct("in Nimbus Teer today")

    assert result.text == "in Nimbus Tier today"


def test_multi_word_correction_reports_what_it_heard():
    corrector = Corrector(glossary("Nimbus Tier"))

    result = corrector.correct("the Nimbus Teer held")

    assert result.hits[0].heard == "Nimbus Teer"
    assert result.hits[0].canonical == "Nimbus Tier"


def test_does_not_merge_unrelated_adjacent_words():
    corrector = Corrector(glossary("Nimbus Tier"))

    result = corrector.correct("the number of trades")

    assert result.text == "the number of trades"
