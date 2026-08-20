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


def test_does_not_absorb_a_longer_word_that_starts_with_a_term():
    # "crimson" is ordinary English that happens to begin with "CRIMS".
    # Similarity scoring rewards the shared prefix and rates it 0.83.
    corrector = Corrector(glossary("CRIMS"))

    result = corrector.correct("the crimson binder")

    assert result.text == "the crimson binder"


def test_still_corrects_a_slightly_truncated_term():
    # One missing character is a plausible recognition error, not a real word.
    corrector = Corrector(glossary("Skylark"))

    result = corrector.correct("onto Skylar today")

    assert result.text == "onto Skylark today"


def test_does_not_absorb_a_longer_word_that_ends_with_a_term():
    corrector = Corrector(glossary("Orbex"))

    result = corrector.correct("the superorbex module")

    assert result.text == "the superorbex module"


def test_does_not_turn_a_common_english_word_into_an_acronym():
    """'crimes' scores 0.91 against CRIMS -- but it is an ordinary word."""
    corrector = Corrector(glossary("CRIMS"))

    result = corrector.correct("the crimes were reported")

    assert result.text == "the crimes were reported"


def test_still_corrects_a_non_word_the_recogniser_invented():
    """'rarr' is not English, so it is safe to treat as a misheard ARR."""
    corrector = Corrector(glossary("ARR"))

    result = corrector.correct("rarr grew this quarter")

    assert result.text == "ARR grew this quarter"


def test_common_word_guard_does_not_block_an_exact_term():
    # A firm may well name something after an ordinary word.
    corrector = Corrector(glossary("Bridge"))

    result = corrector.correct("the Bridge report")

    assert result.text == "the Bridge report"


def test_no_common_english_word_is_ever_turned_into_jargon():
    """Property test over the whole shipped word list.

    Over-correction is the failure this system most needs to avoid, so it is
    checked across every common word rather than by example. Removing the
    guard makes this fail: "crimes" scores 0.91 against CRIMS.

    It does not prove the thresholds are safe for words *outside* the list --
    measured separately, those false positives are rare and obscure.
    """
    from pathlib import Path

    from salm.correct import COMMON_WORDS
    from salm.glossary import Glossary

    example = Path(__file__).resolve().parent.parent / "glossary" / "terms.example.yaml"
    corrector = Corrector(Glossary.load(example))

    corrupted = [w for w in COMMON_WORDS if corrector._best_match(w, 1)]

    assert corrupted == []


def spoken(canonical, forms, kind="acronym", expansion="x"):
    from salm.glossary import Term
    return Glossary([Term(canonical=canonical, type=kind, expansion=expansion,
                          spoken_forms=tuple(forms))])


def test_a_spoken_form_is_rewritten_to_the_canonical_term():
    """spoken_forms must work with biasing off, which is the default."""
    corrector = Corrector(spoken("KYC", ["K Y C"]))

    result = corrector.correct("the K Y C review passed")

    assert result.text == "the KYC review passed"


def test_a_near_miss_of_a_spoken_form_is_also_corrected():
    corrector = Corrector(spoken("KYC", ["K Y C"]))

    result = corrector.correct("the K Y See review")

    assert result.text == "the KYC review"


def test_a_spoken_form_does_not_swallow_ordinary_words():
    corrector = Corrector(spoken("KYC", ["K Y C"]))

    result = corrector.correct("we know the answer")

    assert result.text == "we know the answer"
