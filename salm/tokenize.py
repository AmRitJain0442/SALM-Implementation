"""Convert glossary terms into the token sequences the ASR decoder emits.

Only needed by the optional contextual-biasing path. sherpa-onnx expects
hotwords either as plain words plus a bpe.vocab, or as explicit token
sequences -- and this model ships no bpe.vocab. Passing modeling_unit="bpe"
without one segfaults the native library, so token sequences it is.

Reconstructing SentencePiece BPE without the merge table is possible because
token ids in the vocabulary are ordered by merge priority: merging the
adjacent pair with the lowest id reproduces the model's own segmentation.
Verified against tokens read back from real decoder output.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

MARKER = "▁"  # SentencePiece word-start marker


@lru_cache(maxsize=8)
def _vocab(model_dir: str) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for line in (Path(model_dir) / "tokens.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split(" ")
        if len(parts) >= 2:
            ranks[parts[0]] = int(parts[1])
    return ranks


def to_token_sequence(word: str, model_dir: str | Path) -> str | None:
    """Segment a word the way the model would, as space-separated tokens."""
    word = word.strip()
    if not word:
        return None

    ranks = _vocab(str(model_dir))
    symbols = [MARKER + word[0]] + list(word[1:])
    if symbols[0] not in ranks:
        symbols = [MARKER] + list(word)

    while True:
        best_rank, best_at = None, -1
        for i in range(len(symbols) - 1):
            rank = ranks.get(symbols[i] + symbols[i + 1])
            if rank is not None and (best_rank is None or rank < best_rank):
                best_rank, best_at = rank, i
        if best_at < 0:
            break
        symbols[best_at : best_at + 2] = [symbols[best_at] + symbols[best_at + 1]]

    if any(s not in ranks for s in symbols):
        return None
    return " ".join(symbols)


def spell_out(acronym: str) -> str:
    """Token sequence for an acronym said letter by letter ("C R I M S")."""
    letters = re.sub(r"[^A-Za-z]", "", acronym)
    if not letters:
        return ""
    return " ".join([MARKER + letters[0]] + list(letters[1:]))
