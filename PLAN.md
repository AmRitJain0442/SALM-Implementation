# SALM — Plan

Living document. Updated as work proceeds.

**Goal:** a locally-hosted meeting transcriber that gets the firm's internal
jargon right and expands team acronyms — with no audio, transcript, or
dictionary ever leaving the machine.

**Target:** Apple Silicon Mac, 32 GB. Dev on Windows + RTX 3060 (GPU unused —
the pipeline is CPU/ONNX, so dev and prod run identical code).

---

## Architecture (as built)

```
microphone ──► Silero VAD ──► segment at natural pauses
                                    │
                                    ▼
                     Parakeet TDT 0.6B (ONNX, CPU)      ◄── STAGE 1
                     modified_beam_search
                                    │  raw text
                                    ▼
                     filler guard  ("Okay." on silence)
                                    │
                                    ▼
                     glossary correction (fuzzy + Soundex) ◄── STAGE 2a
                                    │
                                    ▼
                     acronym expansion (first use)        ◄── STAGE 2b
                                    │
                                    ▼
                     FastAPI + WebSocket ──► browser captions
                                          └► transcripts/*.md + *.jsonl
```

---

## Status

### Done
- [x] **Phase 0 de-risk** — settled the biasing question with measurements
- [x] `glossary.py` — YAML source of truth, validation, biasing phrases
- [x] `expand.py` — acronym expansion, first-use policy, longest-match
- [x] `correct.py` — fuzzy + Soundex jargon repair, over-correction guards
- [x] `tokenize.py` — BPE reconstruction from token-id merge order
- [x] `asr.py` — Parakeet transcriber + VAD segmenter + filler guard
- [x] `audio.py` — microphone and file sources behind one interface
- [x] `pipeline.py` / `session.py` — composition, testable without hardware
- [x] `server.py` + `web/index.html` — live caption UI
- [x] Git repo, first commit
- [x] `metrics.py` + `eval/run_eval.py` — reproducible recall/WER harness
- [x] Multi-word jargon correction (`Nimbus Tier`, not just single words)
- [x] Latency measured: RTF 0.088, ~0.93 s after speech ends

- [x] Confluence importer — export → candidate YAML for human review
- [x] CLI (`python -m salm serve|transcribe|import-glossary|check`)
- [x] `scripts/setup.py` model downloader + README
- [x] Server tests (routes, websocket handshake, transcript writing)

- [x] Strict glossary validation (unknown fields, bad types, missing canonical)
- [x] Demo mode — replay recordings through the live pipeline (`serve --demo`)
- [x] End-to-end websocket test: audio → VAD → ASR → correct → browser
- [x] macOS setup notes
- [x] Fixed: capture thread crashed when the browser tab closed mid-session
- [x] `web/render.js` extracted and tested (9 node tests, run from pytest too)

### In progress

- [ ] **Live microphone verification** — everything up to the microphone
      boundary is now covered by an end-to-end test through demo mode. What
      remains is one human speaking into a real mic to confirm capture and
      perceived latency.

### Not started
- [ ] Real-audio re-test of contextual biasing (currently disabled on
      synthetic-audio evidence — see MEMORY.md)
- [ ] macOS install/run notes for the target machine

---

## Key decision: biasing is off

The brief specified contextual biasing during transcription. It was built,
measured, and **turned off** because it made things worse:

| configuration | term recall | WER |
|---|---|---|
| transcription only | 8/11 = 73% | 14.3% |
| **+ glossary correction** | **11/11 = 100%** | **6.1%** |
| + biasing @ 3 | 7/11 = 64% | 18.4% |
| + biasing @ 4 | 7/11 = 64% | 28.6% |
| + biasing @ 5 | 6/11 = 55% | 89.8% |

Biasing loses on both metrics at every setting. The correction pass that
replaced it reaches **100% recall while cutting WER by more than half**
(14.3% → 6.1%). Reproduce with `python eval/run_eval.py --biasing`. The biasing code path is kept behind `Config.biasing_enabled` so it can be
re-tested on real human audio, which is the one caveat on the result above.

---

## Out of scope

Speaker diarization; multi-user serving/auth; fine-tuning (biasing and
correction handle a 20–50 term vocabulary without training data); auto-mining
jargon from documents; meeting-bot integration with Teams/Zoom.
