from salm.metrics import word_error_rate, term_recall


def test_identical_text_has_no_errors():
    assert word_error_rate("the quick fox", "the quick fox") == 0.0


def test_one_wrong_word_in_four():
    assert word_error_rate("a b c d", "a b x d") == 0.25


def test_ignores_case_and_punctuation():
    assert word_error_rate("The Quick, Fox.", "the quick fox") == 0.0


def test_counts_insertions_and_deletions():
    assert word_error_rate("a b c", "a b c d") == pytest_approx(1 / 3)
    assert word_error_rate("a b c", "a b") == pytest_approx(1 / 3)


def pytest_approx(v):
    import pytest
    return pytest.approx(v)


def test_term_recall_counts_terms_present_in_the_hypothesis():
    found, total = term_recall(["ARR", "CRIMS"], "our ARR rose")

    assert (found, total) == (1, 2)


def test_term_recall_is_case_insensitive():
    found, total = term_recall(["Nimbus"], "the NIMBUS tier")

    assert (found, total) == (1, 1)


def test_term_recall_requires_a_whole_word():
    # 'ARR' inside 'BARRIER' is not the term.
    found, total = term_recall(["ARR"], "the BARRIER held")

    assert (found, total) == (0, 1)
