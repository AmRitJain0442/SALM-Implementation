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

Measured over the whole corpus (10 jargon clips across two synthetic speakers,
17 expected term occurrences, plus 4 control clips), reproducible with
`python eval/run_eval.py --biasing --scores 3,4,5`:

| configuration | term recall | WER | false |
|---|---|---|---|
| transcription only | 12/17 = 71% | 14.1% | 0 |
| **+ glossary correction** | **17/17 = 100%** | **4.2%** | **0** |
| + contextual biasing @ 3 | 11/17 = 65% | 16.9% | 0 |
| + contextual biasing @ 4 | 9/17 = 53% | 38.0% | 0 |
| + contextual biasing @ 5 | 10/17 = 59% | 84.5% | 0 |

**No score improved recall; every score made it worse.** Biasing loses on both
metrics across the whole corpus. Above ~4 the context graph fires at wrong
positions and corrupts ordinary speech: `"three exceptions"` → `"Quantexceptions"`,
`"Orbeck's"` → `"Quick's"`. At score ≥5 it degenerates into repeating the
hotword. There is no usable window between "no effect" and "damage".

**Why the alternative works.** Parakeet's unbiased baseline already got CRIMS,
Nimbus, Quantex, VectraBridge and Skylark right with no help. Its residual
errors are *near-misses* — `Halberd→Halbert`, `Orbex→Orbeck's` — which is
exactly what fuzzy + phonetic matching against a 20–50 term list recovers.
End-to-end that takes recall to **100% while cutting WER from 14.1% to 4.2%**.

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

**Display markup could be corrupted by a glossary term matching a CSS class.**
The page originally marked up utterances by string-replacing on already-escaped
HTML. A lowercase term — `fix` is entirely plausible in finance (FIX protocol) —
would have matched `class="fix"` and rewritten the markup. `web/render.js` now
computes mark ranges over the *plain* text and renders once, and is covered by
node tests that `pytest` also runs.

---

## Over-correction: measured, then fixed

The guard against turning ordinary English into jargon was asserted for a long
time before it was measured. Measuring it found two real defects.

**1. A term that is a prefix of a longer word.** "crimson" scores **0.83**
against CRIMS because similarity scoring rewards a shared prefix. Fixed by
refusing a match when the heard word is 2+ characters longer and starts or ends
with the term — one extra character is still a plausible recognition error
("Skylar" for "Skylark").

**2. Common words colliding with short acronyms.** Swept the corrector over
370k English words: **317 false corrections**. The dangerous ones were ordinary
speech — `crimes` → CRIMS at 0.91 would fire in any compliance meeting, plus
`rims`, `animus`.

Ratio tuning cannot fix this: `crimes`→`crims` and `RARR`→`ARR` are both a
single edit. The discriminator is that *crimes is a word people say and RARR is
not*. So `salm/data/common_words.txt` ships the 20k most frequent English words,
and a heard word in that list is believed rather than corrected.

**Frequency, not dictionary membership, is the right test.** A full dictionary
contains "halbert" — and `Halbert → Halberd` is precisely a correction we need.
All five corrections that fire in evaluation (halbert, orbeck, rarr, skylar,
quante) sit outside the top 20k; every risky collision sits inside it.

Result: **zero false corrections across all 20k common words**, recall still
100%, WER 4.2%. Residual false positives over the full 370k are obscure
(`crimps`, `arar`, `obex`) or actually desirable (`halberds` → `Halberd`).

Threshold sweep 0.65–0.85 gives identical results, so 0.75 is not perched on a
knife-edge.

---

## Environment

- Model: `models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8` (~650 MB, gitignored)
- VAD: `models/silero_vad.onnx`
- Test audio is generated by Windows SAPI (`scripts/make_test_audio.ps1`) and
  *is* committed — the clips are ~100 KB each, and committing them means the
  README numbers reproduce on a Mac without Windows. Regenerating the corpus
  reproduces the documented results exactly.
- NeMo was installed and then abandoned; it is CUDA/Triton-bound and has no
  Apple Silicon path. Do not reach for it again for this project.
