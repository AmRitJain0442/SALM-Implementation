"""Download the models SALM needs.

Run once after cloning:

    python scripts/setup.py

Roughly 700 MB. Everything is fetched from the sherpa-onnx release page and
cached under models/; after this the system needs no network at all.
"""

from __future__ import annotations

import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models"
ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"

ASR_ARCHIVE = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2"
ASR_DIR = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
VAD_FILE = "silero_vad.onnx"


def report(done: int, total: int) -> None:
    if total <= 0:
        return
    pct = min(100, done * 100 // total)
    bar = "#" * (pct // 3)
    sys.stdout.write(f"\r  [{bar:<33}] {pct:3d}%  {done // 1048576} MB")
    sys.stdout.flush()


def fetch(name: str, destination: Path) -> None:
    if destination.exists():
        print(f"  {name} already present")
        return
    print(f"  downloading {name}")
    tmp = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(f"{BASE}/{name}") as response, tmp.open("wb") as out:
        total = int(response.headers.get("Content-Length", 0))
        done = 0
        while chunk := response.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            report(done, total)
    print()
    tmp.replace(destination)


def main() -> int:
    MODELS.mkdir(parents=True, exist_ok=True)
    print(f"models -> {MODELS}")

    fetch(VAD_FILE, MODELS / VAD_FILE)

    if (MODELS / ASR_DIR / "encoder.int8.onnx").exists():
        print(f"  {ASR_DIR} already present")
    else:
        archive = MODELS / ASR_ARCHIVE
        fetch(ASR_ARCHIVE, archive)
        print("  extracting")
        with tarfile.open(archive, "r:bz2") as tar:
            tar.extractall(MODELS)
        archive.unlink()

    live = ROOT / "glossary" / "terms.yaml"
    example = ROOT / "glossary" / "terms.example.yaml"
    if not live.exists() and example.exists():
        shutil.copy(example, live)
        print(f"  created {live.relative_to(ROOT)} from the example")

    print("\nReady. Check everything with:  python -m salm check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
