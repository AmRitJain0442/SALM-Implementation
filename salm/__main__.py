"""Command line entry point.

    python -m salm serve                  # live captions in the browser
    python -m salm transcribe FILE.wav    # run one recording through the pipeline
    python -m salm import-glossary export.html
    python -m salm check                  # verify models and microphone
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_serve(args) -> int:
    import uvicorn

    from .config import Config
    from .server import create_app

    config = Config()
    config.host, config.port = args.host, args.port
    config.biasing_enabled = args.biasing

    if args.demo is not None:
        clips = [Path(p) for p in args.demo] or sorted(Path("eval/audio").glob("*.wav"))
        missing = [c for c in clips if not c.exists()]
        if missing or not clips:
            print(f"No demo audio found: {missing or 'eval/audio/*.wav'}", file=sys.stderr)
            return 1
        config.demo_audio = tuple(clips)

    missing = [p for p in (config.model_dir, config.vad_model) if not Path(p).exists()]
    if missing:
        print("Missing model files. Run: python scripts/setup.py", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1

    print(f"SALM listening on http://{config.host}:{config.port}")
    if config.demo_audio:
        print(f"demo mode: replaying {len(config.demo_audio)} recordings")
    print(f"glossary: {config.glossary}")
    if config.biasing_enabled:
        print("contextual biasing: ON (measured worse than correction -- see PLAN.md)")
    uvicorn.run(create_app(config), host=config.host, port=config.port, log_level="warning")
    return 0


def cmd_transcribe(args) -> int:
    from .audio import ArrayAudioSource
    from .config import Config
    from .glossary import Glossary
    from .pipeline import Pipeline
    from .session import Session

    config = Config()
    glossary = Glossary.load(config.glossary)
    session = Session(
        model_dir=config.model_dir,
        vad_model=config.vad_model,
        pipeline=Pipeline(glossary, threshold=config.correction_threshold,
                          policy=config.expansion_policy),
        num_threads=config.num_threads,
    )

    for utterance in session.run(ArrayAudioSource.from_wav(args.audio)):
        print(utterance.text)
        if args.show_raw and utterance.raw != utterance.text:
            print(f"    heard: {utterance.raw}")
        for fix in utterance.corrections:
            print(f"    fixed: {fix.heard} -> {fix.canonical} ({fix.score:.2f})")
    return 0


def cmd_import(args) -> int:
    from .importers import parse_file, to_yaml

    try:
        terms = parse_file(args.export)
    except (ValueError, OSError) as exc:
        print(f"Could not read {args.export}: {exc}", file=sys.stderr)
        return 1

    if not terms:
        print(f"No glossary entries found in {args.export}", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_yaml(terms), encoding="utf-8")

    acronyms = sum(1 for t in terms if t["type"] == "acronym")
    print(f"{len(terms)} candidates ({acronyms} acronyms, "
          f"{len(terms)-acronyms} jargon) -> {out}")

    risky = [t["canonical"] for t in terms
             if t["type"] == "acronym" and len(t["canonical"]) <= 3]
    if risky:
        print(f"\n{len(risky)} short acronyms are collision-prone in speech:")
        print(f"  {', '.join(risky)}")
        print("Check these first -- run `python eval/run_eval.py` after merging.")

    print(f"\nReview {out}, then merge into glossary/terms.yaml.")
    return 0


def cmd_check(args) -> int:
    from .config import Config

    config = Config()
    ok = True

    for label, path in [("model", config.model_dir), ("VAD", config.vad_model),
                        ("glossary", config.glossary)]:
        exists = Path(path).exists()
        ok &= exists
        print(f"[{'ok' if exists else '--'}] {label}: {path}")

    try:
        import sounddevice as sd
        device = sd.query_devices(kind="input")
        print(f"[ok] microphone: {device['name']}")
    except Exception as exc:
        print(f"[--] microphone: {exc}")
        ok = False

    if ok:
        from .glossary import Glossary
        print(f"[ok] {len(Glossary.load(config.glossary).terms)} glossary terms loaded")
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="salm", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="live captions in the browser")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--biasing", action="store_true",
                       help="enable contextual biasing (off by default; measured worse)")
    serve.add_argument("--demo", nargs="*", metavar="WAV", default=None,
                       help="replay recordings instead of the microphone; "
                            "no argument replays eval/audio/*.wav")
    serve.set_defaults(func=cmd_serve)

    one = sub.add_parser("transcribe", help="run one recording through the pipeline")
    one.add_argument("audio")
    one.add_argument("--show-raw", action="store_true", help="also print what was heard")
    one.set_defaults(func=cmd_transcribe)

    imp = sub.add_parser("import-glossary",
                         help="glossary export (.md or .html) -> candidate terms")
    imp.add_argument("export")
    imp.add_argument("-o", "--out", default="glossary/candidates.yaml")
    imp.set_defaults(func=cmd_import)

    check = sub.add_parser("check", help="verify models, glossary and microphone")
    check.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
