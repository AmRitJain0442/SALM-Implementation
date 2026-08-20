"""The expected sequences here were read off the model's own output tokens,
so they are ground truth rather than guesses."""
import pytest
from salm.tokenize import to_token_sequence, spell_out

MODEL = "models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"


@pytest.mark.parametrize("word,expected", [
    ("Kubernetes", "▁K u ber n et es"),
    ("EBITDA", "▁E B I T D A"),
    ("ARR", "▁A R R"),
])
def test_reproduces_the_models_own_tokenization(word, expected):
    assert to_token_sequence(word, MODEL) == expected


def test_spells_an_acronym_letter_by_letter():
    assert spell_out("CRIMS") == "▁C R I M S"


def test_returns_none_for_a_word_it_cannot_tokenize():
    assert to_token_sequence("", MODEL) is None
