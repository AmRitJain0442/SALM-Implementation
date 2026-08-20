"""Runtime configuration, with defaults chosen from measured results."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    model_dir: Path = ROOT / "models" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
    vad_model: Path = ROOT / "models" / "silero_vad.onnx"
    glossary: Path = ROOT / "glossary" / "terms.yaml"
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

    host: str = "127.0.0.1"
    port: int = 8000
