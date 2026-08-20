import pytest
from salm.glossary import Glossary, Term
from salm.expand import Expander


def glossary(*terms):
    return Glossary(list(terms))


ARR = Term(canonical="ARR", expansion="Annual Recurring Revenue", type="acronym")


def test_expands_a_known_acronym_on_first_use():
    expander = Expander(glossary(ARR))

    result = expander.expand("our ARR grew")

    assert result.text == "our ARR (Annual Recurring Revenue) grew"


def test_leaves_the_second_use_of_the_same_acronym_unexpanded():
    expander = Expander(glossary(ARR))

    expander.expand("our ARR grew")
    result = expander.expand("ARR again")

    assert result.text == "ARR again"


def test_does_not_match_an_acronym_inside_a_longer_word():
    expander = Expander(glossary(ARR))

    result = expander.expand("the BARRIER held")

    assert result.text == "the BARRIER held"


def test_leaves_unknown_words_untouched():
    expander = Expander(glossary(ARR))

    result = expander.expand("the QQQ metric")

    assert result.text == "the QQQ metric"


def test_reports_which_terms_fired():
    expander = Expander(glossary(ARR))

    result = expander.expand("our ARR grew")

    assert [hit.canonical for hit in result.hits] == ["ARR"]


def test_a_longer_term_wins_over_a_shorter_one_nested_inside_it():
    expander = Expander(glossary(
        Term(canonical="ARR", expansion="Annual Recurring Revenue", type="acronym"),
        Term(canonical="ARR Bridge", expansion="ARR Bridge Report", type="acronym"),
    ))

    result = expander.expand("review the ARR Bridge today")

    assert result.text == "review the ARR Bridge (ARR Bridge Report) today"


def test_jargon_without_an_expansion_is_left_alone():
    expander = Expander(glossary(Term(canonical="Kubernetes", type="jargon")))

    result = expander.expand("deploy on Kubernetes")

    assert result.text == "deploy on Kubernetes"
    assert result.hits == ()
