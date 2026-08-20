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

On 10 jargon clips across two speakers (17 term occurrences), plus 4 control
clips of ordinary speech containing no jargon at all
(`python eval/run_eval.py --biasing`):

| configuration | jargon term recall | word error rate | false corrections |
|---|---|---|---|
| transcription only | 12/17 = 71% | 14.1% | 0 |
| **+ glossary correction** | **17/17 = 100%** | **4.2%** | **0** |
| + contextual biasing @ 3 | 11/17 = 65% | 16.9% | 0 |
| + contextual biasing @ 4 | 9/17 = 53% | 38.0% | 0 |
| + contextual biasing @ 5 | 10/17 = 59% | 84.5% | 0 |

The third column is the one that is easy to forget. Turning ordinary English
into jargon is worse than leaving a term misspelled, so the control clips exist
to catch it — and the corrector was swept over 370,000 English words to make
sure. `crimes` scores 0.91 against `CRIMS`; without a guard it would be
rewritten in every compliance meeting.

**Contextual biasing is implemented but disabled by default.** It was the
original plan — bias the decoder toward the glossary so jargon is spelled
correctly at recognition time. Measured, it lost at every setting: recall fell
rather than rose, and word error rate climbed as the context graph fired at
wrong positions (`"three exceptions"` became `"Quantexceptions"`). Correcting
after the fact reaches full term recall while cutting WER by more than two
thirds.

Enable it anyway with `python -m salm serve --biasing` if you want to re-measure
on your own audio. See [`MEMORY.md`](MEMORY.md) for the details.

> **Caveat:** the corpus is synthetic speech from Windows SAPI, not human
> recordings. The direction is consistent and large, but confirm on real voices
> before treating these numbers as final.

## Quickstart

```bash
git clone https://github.com/AmRitJain0442/SALM-Implementation.git
cd SALM-Implementation
pip install -r requirements.txt
python scripts/setup.py      # downloads ~700 MB of models, once
python -m salm check         # verifies models, glossary, microphone
python -m salm serve         # http://127.0.0.1:8000
```

The glossary ships with the repository, so there is nothing else to set up.

No microphone handy, or demoing to a room? Replay the sample recordings
through the live pipeline instead:

```bash
python -m salm serve --demo            # replays eval/audio/*.wav
python -m salm serve --demo a.wav b.wav
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

`spoken_forms` is for anything said differently from how it is written. An
acronym dictated letter by letter often reaches the transcript as `K Y C`, and
listing that form maps it back to `KYC`. Near-misses of a spoken form are
recovered too, so `K Y See` also resolves.

**Terms take effect on the next session — no restart.** Edit the file, press
Stop then Start, and the new terms are live. A malformed file is reported in
the status bar rather than failing silently.

`glossary/terms.yaml` is committed, so a clone comes with the vocabulary
already in place — nothing to copy across. `glossary/terms.example.yaml` holds
invented terms and is what the test suite reads, so tests never depend on the
real glossary.

### Importing an existing glossary

```bash
python -m salm import-glossary glossary-export.md     # Markdown tables
python -m salm import-glossary confluence-export.html # HTML exports
```

This writes `glossary/candidates.yaml` for a human to review, and deliberately
never writes `terms.yaml` directly: a wrong entry silently corrupts correction
for every meeting afterwards. The importer helps by:

- classifying acronyms from jargon, and generating spelled forms only for real
  initialisms — `ASP` is said "A S P", but `GREEN` meaning "Band 4" is not said
  "G R E E N", and the giveaway is whether the letters match the expansion's
  initials;
- stripping a meaning that repeats its own term, so `GREEN | GREEN (Band 4)`
  does not expand to `GREEN (GREEN (Band 4))`;
- flagging expansions too long or too structured to read inline;
- listing short acronyms, which are the ones that collide with ordinary speech.

`glossary/candidates.yaml` is gitignored — import scratch output stays local
until you have reviewed it and merged what you want into `terms.yaml`.

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
term misspelled, so the recogniser is believed whenever it produces one of the
20,000 most frequent English words, and a term is never allowed to swallow a
longer word that merely starts with it.

Frequency matters more than dictionary membership here. A full dictionary also
contains `halbert` — and `Halbert → Halberd` is exactly a correction worth
keeping.

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

Measured on the Windows development machine at 4 threads: real-time factor
**0.088**, about 11x faster than real time. For a six-second utterance, text
appears roughly **0.9 s** after the speaker stops — VAD silence confirmation
plus decode. Model load is 2.7 s, once at startup.

### On macOS (the target platform)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/setup.py
python -m salm check
```

Two things specific to macOS:

- **Microphone permission.** The first run must be allowed to record. If
  `salm check` reports no input device, grant your terminal access under
  System Settings → Privacy & Security → Microphone, then restart the terminal.
  macOS does not re-prompt.
- **Threads.** `Config.num_threads` defaults to 4. On an M-series chip, setting
  it to the number of performance cores is usually worth a little latency.

No Rosetta and no Homebrew packages are needed: `sherpa-onnx` and `sounddevice`
both ship arm64 wheels.

## Tests

```bash
python -m pytest tests/ -q
```

The suite covers the glossary, correction, expansion, tokenization and metrics
as unit tests, and exercises the model end-to-end on real audio.
