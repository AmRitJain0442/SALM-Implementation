"""Measure the pipeline: does it get the firm's jargon right, and at what cost?

Three numbers, and all three matter:

  recall  did the firm's jargon come out spelled correctly?
  WER     did the rest of the sentence survive intact?
  false   how often did ordinary English get turned into jargon?

`false` is the one that is easy to forget and expensive to get wrong. It is
measured on control clips that contain no glossary terms at all, seeded with
words that sit phonetically close to them. Any correction that fires there is a
false positive.

    python eval/run_eval.py
    python eval/run_eval.py --biasing        # include the disabled biasing path
    python eval/run_eval.py --sweep          # tune the correction threshold
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salm.asr import Transcriber, is_filler                # noqa: E402
from salm.audio import ArrayAudioSource                    # noqa: E402
from salm.config import Config                             # noqa: E402
from salm.correct import Corrector                         # noqa: E402
from salm.glossary import Glossary                         # noqa: E402
from salm.metrics import term_recall, word_error_rate      # noqa: E402
from salm.tokenize import spell_out, to_token_sequence     # noqa: E402


def load_manifest(path: Path) -> tuple[list[dict], list[dict]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["clips"], data.get("controls", [])


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


def transcribe_all(clips: list[dict], transcriber: Transcriber) -> dict[str, str]:
    """Decode once; every configuration below reuses these hypotheses."""
    out = {}
    for clip in clips:
        samples = ArrayAudioSource.from_wav(clip["audio"])._samples
        out[clip["audio"]] = transcriber.transcribe(samples)
    return out


def score(clips, controls, heard: dict[str, str], corrector: Corrector | None) -> dict:
    found = expected = 0
    errors = words = 0.0
    misses = []

    for clip in clips:
        text = heard[clip["audio"]]
        if corrector and not is_filler(text):
            text = corrector.correct(text).text

        hit, total = term_recall(clip["terms"], text)
        found, expected = found + hit, expected + total
        if hit < total:
            misses.append((clip["terms"], text))

        length = len(clip["text"].split())
        errors += word_error_rate(clip["text"], text) * length
        words += length

    # Control clips hold no glossary terms; anything the corrector changes here
    # is ordinary English being turned into jargon.
    false_positives = []
    for clip in controls:
        text = heard[clip["audio"]]
        if corrector and not is_filler(text):
            result = corrector.correct(text)
            false_positives.extend(
                (hit.heard, hit.canonical) for hit in result.hits
            )

    return {
        "recall": found / expected if expected else 0.0,
        "found": found, "expected": expected,
        "wer": errors / words if words else 0.0,
        "false": false_positives,
        "misses": misses,
    }


def show(rows: list[tuple[str, dict]]) -> None:
    width = max(len(name) for name, _ in rows)
    print(f"{'configuration'.ljust(width)}   term recall       WER    false")
    print("-" * (width + 36))
    for name, r in rows:
        print(f"{name.ljust(width)}   {r['found']}/{r['expected']} = "
              f"{r['recall']*100:3.0f}%  {r['wer']*100:6.1f}%   {len(r['false']):5d}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default="eval/manifest.yaml")
    parser.add_argument("--biasing", action="store_true",
                        help="also evaluate the disabled contextual-biasing path")
    parser.add_argument("--scores", default="3,4",
                        help="comma-separated biasing scores to try")
    parser.add_argument("--sweep", action="store_true",
                        help="sweep the correction threshold")
    args = parser.parse_args()

    config = Config()
    clips, controls = load_manifest(Path(args.manifest))
    glossary = Glossary.load(config.glossary)
    print(f"{len(clips)} jargon clips, {len(controls)} control clips, "
          f"{len(glossary.terms)} glossary terms\n")

    started = time.time()
    plain = Transcriber(config.model_dir, num_threads=config.num_threads)
    heard = transcribe_all(clips + controls, plain)
    print(f"decoded {len(heard)} clips in {time.time()-started:.1f}s\n")

    rows: list[tuple[str, dict]] = []
    rows.append(("transcription only", score(clips, controls, heard, None)))

    if args.sweep:
        for threshold in (0.65, 0.70, 0.75, 0.80, 0.85):
            rows.append((f"+ correction @ {threshold:.2f}",
                         score(clips, controls, heard,
                               Corrector(glossary, threshold=threshold))))
    else:
        rows.append((f"+ correction @ {config.correction_threshold:.2f}",
                     score(clips, controls, heard,
                           Corrector(glossary, threshold=config.correction_threshold))))

    if args.biasing:
        phrases = hotword_list(glossary, config.model_dir)
        for value in [float(s) for s in args.scores.split(",")]:
            biased = Transcriber(config.model_dir, num_threads=config.num_threads,
                                 hotwords=phrases, hotwords_score=value)
            rows.append((f"+ biasing @ {value:g}",
                         score(clips, controls, transcribe_all(clips + controls, biased), None)))

    show(rows)

    # Prefer recall, then fewest false positives, then lowest WER.
    best = max(rows, key=lambda r: (r[1]["recall"], -len(r[1]["false"]), -r[1]["wer"]))
    print(f"\nbest: {best[0]}")
    for terms, text in best[1]["misses"]:
        print(f"  missed {terms}: {text!r}")
    for heard_word, canonical in best[1]["false"]:
        print(f"  FALSE POSITIVE {heard_word!r} -> {canonical!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
