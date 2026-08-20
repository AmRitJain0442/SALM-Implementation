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

### In progress
- [ ] Evaluation harness (`eval/`) — measure recall/WER over the whole corpus
- [ ] Confluence importer — export → candidate YAML for human review
- [ ] CLI entry point + README
- [ ] Live microphone verification end-to-end

### Not started
- [ ] Real-audio re-test of contextual biasing (currently disabled on
      synthetic-audio evidence — see MEMORY.md)
- [ ] macOS install/run notes for the target machine

---

## Key decision: biasing is off

The brief specified contextual biasing during transcription. It was built,
measured, and **turned off** because it made things worse:

| config | jargon recall | WER |
|---|---|---|
| biasing off | 75% | **13.8%** |
| biasing score 3 | 75% | 17.2% |
| biasing score 4 | 75% | 31.0% |

Zero recall gain, monotonically worse WER, no usable operating window. The
correction pass that replaced it takes recall **78% → 100%** while *lowering*
WER. The biasing code path is kept behind `Config.biasing_enabled` so it can be
re-tested on real human audio, which is the one caveat on the result above.

---

## Out of scope

Speaker diarization; multi-user serving/auth; fine-tuning (biasing and
correction handle a 20–50 term vocabulary without training data); auto-mining
jargon from documents; meeting-bot integration with Teams/Zoom.
