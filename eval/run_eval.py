"""Measure the pipeline: does it get the firm's jargon right, and at what cost?

Runs the corpus in eval/manifest.yaml through several configurations and prints
a comparison. Read both columns together -- a configuration that lifts term
recall while raising word error rate is trading ordinary speech for jargon, and
is usually a bad trade.

    python eval/run_eval.py
    python eval/run_eval.py --biasing        # include the disabled biasing path
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salm.asr import Transcriber, is_filler          # noqa: E402
from salm.config import Config                        # noqa: E402
from salm.correct import Corrector                    # noqa: E402
from salm.expand import Expander                      # noqa: E402
from salm.glossary import Glossary                    # noqa: E402
from salm.metrics import term_recall, word_error_rate  # noqa: E402
from salm.tokenize import spell_out, to_token_sequence  # noqa: E402
from salm.audio import ArrayAudioSource                # noqa: E402


def load_clips(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["clips"]


def hotword_list(glossary: Glossary, model_dir: Path) -> list[str]:
    """Glossary terms as decoder token sequences, for the biasing path."""
    phrases = []
    for term in glossary.terms:
        sequence = (
            spell_out(term.canonical)
            if term.type == "acronym"
            else to_token_sequence(term.canonical, model_dir)
        )
        if sequence:
            phrases.append(sequence)
    return phrases


def evaluate(clips, transcriber, glossary, correct: bool, config: Config) -> dict:
    corrector = Corrector(glossary, threshold=config.correction_threshold)
    found = expected = 0
    errors = words = 0.0
    elapsed = 0.0
    examples = []

    for clip in clips:
        samples = ArrayAudioSource.from_wav(clip["audio"])._samples
        start = time.time()
        raw = transcriber.transcribe(samples)
        elapsed += time.time() - start

        text = raw
        if correct and not is_filler(raw):
            text = corrector.correct(raw).text

        hit, total = term_recall(clip["terms"], text)
        found += hit
        expected += total

        rate = word_error_rate(clip["text"], text)
        reference_len = len(clip["text"].split())
        errors += rate * reference_len
        words += reference_len

        if hit < total:
            examples.append((clip["terms"], text))

    return {
        "recall": found / expected,
        "found": found,
        "expected": expected,
        "wer": errors / words,
        "seconds": elapsed,
        "misses": examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="eval/manifest.yaml")
    parser.add_argument("--biasing", action="store_true",
                        help="also evaluate the disabled contextual-biasing path")
    parser.add_argument("--scores", default="3,4",
                        help="comma-separated biasing scores to try")
    args = parser.parse_args()

    config = Config()
    clips = load_clips(Path(args.manifest))
    glossary = Glossary.load(config.glossary)
    print(f"{len(clips)} clips, {len(glossary.terms)} glossary terms\n")

    runs: list[tuple[str, dict]] = []

    plain = Transcriber(config.model_dir, num_threads=config.num_threads)
    runs.append(("transcription only", evaluate(clips, plain, glossary, False, config)))
    runs.append(("+ glossary correction", evaluate(clips, plain, glossary, True, config)))

    if args.biasing:
        phrases = hotword_list(glossary, config.model_dir)
        for score in [float(s) for s in args.scores.split(",")]:
            biased = Transcriber(
                config.model_dir, num_threads=config.num_threads,
                hotwords=phrases, hotwords_score=score,
            )
            runs.append((f"+ biasing @ {score:g}",
                         evaluate(clips, biased, glossary, False, config)))

    width = max(len(name) for name, _ in runs)
    print(f"{'configuration'.ljust(width)}   term recall        WER    decode")
    print("-" * (width + 38))
    for name, r in runs:
        print(f"{name.ljust(width)}   {r['found']}/{r['expected']} = "
              f"{r['recall']*100:3.0f}%   {r['wer']*100:6.1f}%   {r['seconds']:5.1f}s")

    best = max(runs, key=lambda r: (r[1]["recall"], -r[1]["wer"]))
    print(f"\nbest: {best[0]}")
    for terms, text in best[1]["misses"]:
        print(f"  still missing {terms}: {text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
