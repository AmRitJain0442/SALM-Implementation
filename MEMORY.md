# SALM — Working memory

Findings and decisions worth not rediscovering. Newest section last.

---

## Hard-won facts about sherpa-onnx

**`modeling_unit="bpe"` without a `bpe.vocab` segfaults the process.**
Not an exception — SIGSEGV inside the native library, exit 139, no traceback.
`parakeet-tdt-0.6b-v2-int8` ships `tokens.txt` only, no `bpe.vocab`. The code
pins `modeling_unit="cjkchar"` and passes hotwords as explicit token sequences.

**`modified_beam_search` is meaningfully more accurate than `greedy_search`.**
Same clip, same model: greedy → `"CubaNets"`, beam → `"Kubernetes"`. Costs a few
ms per segment. It is the default in `asr.py` regardless of biasing. An earlier
guess that beam search silently falls back to greedy for TDT was **wrong**.

**Hotwords must be `▁`-prefixed token sequences**, e.g. `▁A R R`, not plain
words, given no `bpe.vocab`.

**BPE tokenization can be reconstructed without SentencePiece.** Token ids in
`tokens.txt` are ordered by merge priority, so repeatedly merging the adjacent
pair with the lowest id reproduces the model's own segmentation. Verified exact
against tokens read back from real decoder output for Kubernetes, EBITDA, ARR.
This matters: greedy longest-match gives `▁K ub er ne te s` where the model
actually uses `▁K u ber n et es`, and that mismatch actively corrupts decoding.

**The model hallucinates on silence.** Pure digital silence decodes as
`"Okay."`; low noise as `"Mm-hmm."`. VAD catches most of it; `is_filler()` in
`asr.py` catches the rest. Without both, a live transcript fills with `Okay.`

---

## The biasing result (the project's main finding)

Measured over the whole corpus (7 clips, 11 expected term occurrences),
reproducible with `python eval/run_eval.py --biasing --scores 3,4,5`:

| configuration | term recall | WER |
|---|---|---|
| transcription only | 8/11 = 73% | 14.3% |
| **+ glossary correction** | **11/11 = 100%** | **6.1%** |
| + biasing @ 3 | 7/11 = 64% | 18.4% |
| + biasing @ 4 | 7/11 = 64% | 28.6% |
| + biasing @ 5 | 6/11 = 55% | 89.8% |

**No score improved recall; every score made it worse.** On the full
7-clip corpus biasing loses on *both* metrics. Above ~4 the context graph fires at wrong
positions and corrupts ordinary speech: `"three exceptions"` → `"Quantexceptions"`,
`"Orbeck's"` → `"Quick's"`. At score ≥5 it degenerates into repeating the
hotword. There is no usable window between "no effect" and "damage".

**Why the alternative works.** Parakeet's unbiased baseline already got CRIMS,
Nimbus, Quantex, VectraBridge and Skylark right with no help. Its residual
errors are *near-misses* — `Halberd→Halbert`, `Orbex→Orbeck's` — which is
exactly what fuzzy + phonetic matching against a 20–50 term list recovers.
End-to-end that takes recall to **100% while cutting WER from 14.3% to 6.1%**.

**Caveat, stated plainly:** all of this is synthetic Windows SAPI speech, not
human audio. The direction is strong and consistent, but real-voice
confirmation is still outstanding. That is why the biasing path was kept behind
a config flag rather than deleted.

---

## Design decisions and why

**Deterministic correction, not an LLM.** 20–50 mostly-unique terms means a
lookup table cannot hallucinate, is auditable, needs no memory the ASR wants,
and runs in microseconds. `expand.py` keeps a seam for a disambiguator if real
transcripts ever show acronym clashes.

**Offline model + VAD, not a streaming model.** The latency budget is 3–5 s and
audio is mic-only, so VAD can cut at natural pauses and hand a full utterance to
a more accurate offline model. Better accuracy than streaming, still live.

**Correction runs before expansion.** An acronym misheard as `Crims` must be
repaired before it can be looked up.

**Over-correction is the real risk in `correct.py`.** Turning ordinary English
into jargon is worse than leaving a term misspelled, so: a `COMMON_WORDS`
denylist, a 0.75 similarity floor, and a lower 0.6 floor *only* when Soundex
keys also match. Soundex was added because `Orbeck's`→`Orbex` scores 0.727 —
below threshold on spelling, but phonetically identical, which is precisely the
error mode ASR produces.

**No webfonts in the UI.** A tool whose promise is "nothing leaves the machine"
must not fetch from a font CDN on every page load. System stacks only. The UI
uses serif for corrected transcript text and mono for raw machine output, so
the typography itself shows the two stages.

---

## Performance (measured, Windows dev box, 4 threads)

Real-time factor **0.088** — 11x faster than real time — consistently across
all clips. Model load is 2.7 s, once at startup.

Latency after a speaker stops, for a 6 s utterance:

| stage | cost |
|---|---|
| VAD silence confirmation | 0.40 s |
| decode (6 s x 0.088) | 0.53 s |
| **total** | **~0.93 s** |

Comfortably inside the 3–5 s budget, with headroom to spare. There is room to
raise `max_speech_duration` or lower `min_silence_duration` if longer context
turns out to help accuracy.

---

## Bugs found and fixed

**Capture thread died when the browser tab closed.** The session runs on a
worker thread and publishes to the websocket's asyncio loop. Closing the tab
closes that loop, and the next `call_soon_threadsafe` raised
`RuntimeError: Event loop is closed` *on the worker thread*, killing the session
mid-meeting. `SessionManager._publish` now checks `loop.is_closed()` and
swallows the race. Dropping the message is safe: utterances are kept in memory
and still reach the saved transcript.

Found because pytest surfaced it as `PytestUnhandledThreadExceptionWarning`
rather than a failure — worth keeping test output pristine for exactly this
reason.

---

## Environment

- Model: `models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8` (~650 MB, gitignored)
- VAD: `models/silero_vad.onnx`
- Test audio is generated by Windows SAPI via PowerShell `System.Speech`;
  see `scripts/` — regenerate rather than commit large audio.
- NeMo was installed and then abandoned; it is CUDA/Triton-bound and has no
  Apple Silicon path. Do not reach for it again for this project.
