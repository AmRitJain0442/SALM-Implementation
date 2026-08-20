"""Compare ASR engines on the same corpus, with the same glossary and metrics.

The choice of recogniser is the single biggest decision in this project, so it
should be measured rather than argued. This runs each engine over
eval/manifest.yaml and reports what actually matters here:

  recall   did the jargon come out spelled correctly?
  WER      did the rest of the sentence survive?
  RTF      real-time factor -- decode seconds per audio second, on CPU
  size     on-disk footprint, which is what a laptop pays for

Engines are discovered from whatever is present in models/, so add a model
directory and it appears in the comparison.

    python eval/compare_engines.py
    python eval/compare_engines.py --corrected   # with the glossary pass applied
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import sherpa_onnx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salm.audio import ArrayAudioSource                # noqa: E402
from salm.config import Config                         # noqa: E402
from salm.correct import Corrector                     # noqa: E402
from salm.glossary import Glossary                     # noqa: E402
from salm.metrics import term_recall, word_error_rate  # noqa: E402

MODELS = Path(__file__).resolve().parent.parent / "models"


def directory_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def build_parakeet(path: Path, threads: int):
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(path / "encoder.int8.onnx"),
        decoder=str(path / "decoder.int8.onnx"),
        joiner=str(path / "joiner.int8.onnx"),
        tokens=str(path / "tokens.txt"),
        model_type="nemo_transducer",
        num_threads=threads,
        decoding_method="modified_beam_search",
    )


def build_whisper(path: Path, threads: int):
    """Whisper ships encoder/decoder pairs; prefer the int8 quantised ones."""
    def pick(role: str) -> str:
        quantised = list(path.glob(f"*{role}.int8.onnx"))
        return str(quantised[0] if quantised else next(iter(path.glob(f"*{role}.onnx"))))

    return sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=pick("encoder"),
        decoder=pick("decoder"),
        tokens=str(next(iter(path.glob("*tokens.txt")))),
        num_threads=threads,
        language="en",
        task="transcribe",
    )


def discover(threads: int) -> list[tuple[str, Path, object]]:
    engines = []
    for path in sorted(MODELS.iterdir()):
        if not path.is_dir():
            continue
        try:
            if (path / "joiner.int8.onnx").exists():
                engines.append((path.name.replace("sherpa-onnx-nemo-", ""),
                                path, build_parakeet(path, threads)))
            elif list(path.glob("*decoder*.onnx")) and "whisper" in path.name:
                engines.append((path.name.replace("sherpa-onnx-", ""),
                                path, build_whisper(path, threads)))
        except Exception as exc:                       # report, never skip silently
            print(f"  could not load {path.name}: {type(exc).__name__}: {exc}")
    return engines


def evaluate(recognizer, clips, controls, corrector) -> dict:
    found = expected = 0
    errors = words = 0.0
    audio_seconds = decode_seconds = 0.0
    false_positives = 0
    misses = []

    for clip in clips + controls:
        samples = ArrayAudioSource.from_wav(clip["audio"])._samples
        audio_seconds += len(samples) / 16000

        stream = recognizer.create_stream()
        stream.accept_waveform(16000, samples)
        started = time.time()
        recognizer.decode_stream(stream)
        decode_seconds += time.time() - started
        text = stream.result.text

        if corrector:
            result = corrector.correct(text)
            text = result.text
            if "terms" not in clip:
                false_positives += len(result.hits)

        if "terms" in clip:
            hit, total = term_recall(clip["terms"], text)
            found, expected = found + hit, expected + total
            if hit < total:
                misses.append((clip["terms"], text))

        length = len(clip["text"].split())
        errors += word_error_rate(clip["text"], text) * length
        words += length

    return {
        "recall": found / expected if expected else 0.0,
        "found": found, "expected": expected,
        "wer": errors / words if words else 0.0,
        "rtf": decode_seconds / audio_seconds if audio_seconds else 0.0,
        "false": false_positives,
        "misses": misses,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default="eval/manifest.yaml")
    parser.add_argument("--corrected", action="store_true",
                        help="apply the glossary correction pass")
    args = parser.parse_args()

    config = Config()
    data = yaml.safe_load(Path(args.manifest).read_text(encoding="utf-8"))
    clips, controls = data["clips"], data.get("controls", [])
    glossary = Glossary.load(data.get("glossary") or config.glossary)
    corrector = Corrector(glossary) if args.corrected else None

    print(f"{len(clips)} jargon clips, {len(controls)} controls, "
          f"{config.num_threads} threads, "
          f"correction {'on' if args.corrected else 'off'}\n")

    engines = discover(config.num_threads)
    if not engines:
        print("No models found in models/", file=sys.stderr)
        return 1

    rows = []
    for name, path, recognizer in engines:
        rows.append((name, directory_size(path), evaluate(recognizer, clips, controls, corrector)))

    width = max(len(n) for n, _, _ in rows)
    print(f"{'engine'.ljust(width)}   {'size':>7}  term recall      WER     RTF")
    print("-" * (width + 42))
    for name, size, r in sorted(rows, key=lambda x: (-x[2]["recall"], x[2]["wer"])):
        print(f"{name.ljust(width)}   {size/1e6:6.0f}M  "
              f"{r['found']}/{r['expected']} = {r['recall']*100:3.0f}%  "
              f"{r['wer']*100:6.1f}%  {r['rtf']:6.3f}")

    print()
    for name, _, r in rows:
        for terms, text in r["misses"]:
            print(f"  {name}: missed {terms} -> {text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
