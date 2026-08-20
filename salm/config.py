"""Runtime configuration, with defaults chosen from measured results."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _glossary_path() -> Path:
    """The live glossary if present, otherwise the shipped example.

    The real dictionary is gitignored: it is firm-proprietary, and this repo
    is public. Falling back keeps a fresh clone runnable.
    """
    live = ROOT / "glossary" / "terms.yaml"
    return live if live.exists() else ROOT / "glossary" / "terms.example.yaml"


@dataclass
class Config:
    model_dir: Path = ROOT / "models" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
    vad_model: Path = ROOT / "models" / "silero_vad.onnx"
    glossary: Path = field(default_factory=_glossary_path)
    transcript_dir: Path = ROOT / "transcripts"
    num_threads: int = 4

    # Correction confidence. Raise it if ordinary words get turned into jargon;
    # lower it if near-miss jargon is being left uncorrected.
    correction_threshold: float = 0.75

    # first_use | always | never
    expansion_policy: str = "first_use"

    # Contextual biasing, off by default: measured worse than correction on
    # every axis for this model. Kept so it can be re-tested on real audio.
    biasing_enabled: bool = False
    hotwords_score: float = 3.0

    # Replay recordings instead of opening the microphone. Lets the demo run
    # without anyone speaking, and without a working input device.
    demo_audio: tuple[Path, ...] = ()
    # Pace the replay like real speech. Tests turn this off to run fast.
    demo_realtime: bool = True

    host: str = "127.0.0.1"
    port: int = 8000
