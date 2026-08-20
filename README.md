# SALM

Live meeting transcription that gets your firm's internal language right, and
never sends a byte off the machine.

General speech recognition mangles firm-internal vocabulary: product names come
out as phonetically-similar nonsense, and acronyms stay opaque to anyone outside
the team. Sending meeting audio to a cloud vendor to fix that is not an option
when the audio, the transcripts, and the glossary are all proprietary.

SALM runs a two-stage pipeline entirely on local hardware:

1. **Transcribe** — Parakeet TDT 0.6B via ONNX Runtime, on CPU.
2. **Repair and expand** — a deterministic pass over your glossary fixes
   near-miss jargon and expands acronyms on first use.

```
heard   Orbeck's reconciliation runs before the CRIMS batch.
output  Orbex reconciliation runs before the CRIMS (Client Risk Management System) batch.
```

## Measured results

On a 7-clip corpus containing 11 jargon occurrences
(`python eval/run_eval.py --biasing`):

| configuration | jargon term recall | word error rate |
|---|---|---|
| transcription only | 8/11 = 73% | 14.3% |
| **+ glossary correction** | **11/11 = 100%** | **6.1%** |
| + contextual biasing @ 3 | 7/11 = 64% | 18.4% |
| + contextual biasing @ 5 | 6/11 = 55% | 89.8% |

**Contextual biasing is implemented but disabled by default.** It was the
original plan — bias the decoder toward the glossary so jargon is spelled
correctly at recognition time. Measured, it lost on both metrics at every
setting: no recall gain, and rising word error rate as the context graph fired
at wrong positions (`"three exceptions"` became `"Quantexceptions"`). Correcting
after the fact reaches full term recall while *more than halving* WER.

Enable it anyway with `python -m salm serve --biasing` if you want to re-measure
on your own audio. See [`MEMORY.md`](MEMORY.md) for the details.

> **Caveat:** the corpus is synthetic speech from Windows SAPI, not human
> recordings. The direction is consistent and large, but confirm on real voices
> before treating these numbers as final.

## Quickstart

```bash
pip install -r requirements.txt
python scripts/setup.py      # downloads ~700 MB of models, once
python -m salm check         # verifies models, glossary, microphone
python -m salm serve         # http://127.0.0.1:8000
```

Then open the page and press **Start listening**. Corrected terms are marked in
the transcript with what was actually heard beside them, so every change the
system makes is visible rather than silent.

Other commands:

```bash
python -m salm transcribe meeting.wav --show-raw
python -m salm import-glossary confluence-export.html
python eval/run_eval.py
```

## The glossary

`glossary/terms.yaml` is the single source of truth for both stages, so the
correction table and the expansion table cannot drift apart.

```yaml
terms:
  - canonical: CRIMS
    expansion: Client Risk Management System
    type: acronym
    spoken_forms: ["C R I M S"]

  - canonical: Skylark
    type: jargon          # corrected for spelling; not expanded
```

Acronyms are expanded on first use per session and left bare afterwards, which
keeps a long transcript readable. Jargon is only spelled correctly — rewriting
every mention of a product name with its definition makes transcripts unusable.

**The live glossary is gitignored.** Your firm's term list is proprietary and
this repository is public, so `glossary/terms.yaml` never leaves your machine;
`glossary/terms.example.yaml` ships in its place and is copied on setup.

To import an existing glossary, `import-glossary` writes
`glossary/candidates.yaml` for a human to review. It deliberately never writes
`terms.yaml` directly: a wrong entry silently corrupts correction for every
meeting afterwards.

## How it works

```
microphone ──► Silero VAD ──► segment at natural pauses
                                     │
                                     ▼
                    Parakeet TDT 0.6B (ONNX, CPU)
                    modified_beam_search
                                     │  raw text
                                     ▼
                    filler guard   (the model says "Okay." to silence)
                                     │
                                     ▼
                    glossary correction  (similarity + Soundex)
                                     │
                                     ▼
                    acronym expansion    (first use)
                                     │
                                     ▼
                    WebSocket ──► browser  +  transcripts/*.md, *.jsonl
```

Two choices worth explaining:

**An offline model with VAD, rather than a streaming model.** With a 3–5 second
latency budget, voice activity detection can cut speech at natural pauses and
hand a complete utterance to a more accurate offline model. You get better
accuracy than streaming while the text still appears during the meeting.

**Similarity *and* phonetics for correction.** `Orbeck's` → `Orbex` scores 0.73
on spelling — below the safety threshold — but the two are phonetically
identical, which is exactly how speech recognition fails. A Soundex match lowers
the threshold only when the words genuinely sound alike. The greater risk is
over-correction: turning ordinary English into jargon is worse than leaving a
term misspelled, so ordinary words are protected by a denylist and a
conservative floor.

## Privacy

- No network access at runtime. Models are downloaded once by `scripts/setup.py`.
- No webfonts or CDNs in the UI — a page that phones out on every load would
  defeat the point.
- Audio is never written to disk. Transcripts are written only to `transcripts/`,
  which is gitignored.
- The glossary stays local, as above.

## Requirements

Python 3.10+. Runs on CPU; no GPU required. Developed on Windows, targeted at
Apple Silicon — the same code path runs on both, which is why ONNX Runtime was
chosen over a CUDA-bound toolkit.

## Tests

```bash
python -m pytest tests/ -q
```

The suite covers the glossary, correction, expansion, tokenization and metrics
as unit tests, and exercises the model end-to-end on real audio.
