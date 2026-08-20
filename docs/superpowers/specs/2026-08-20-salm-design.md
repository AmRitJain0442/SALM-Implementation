# SALM — Design

**Status:** superseded Stage 1 engine on 2026-08-20 (see "Architecture change").

## Problem

Meeting transcription fails on firm-internal language: proprietary product names
and team jargon come out as phonetically-similar nonsense, and acronyms stay
opaque to anyone outside the team. Cloud ASR is not an option — the audio,
transcripts, and the jargon dictionary itself are proprietary.

## Two-stage pipeline

1. **Biased transcription** — the ASR decoder is biased toward the firm's term
   list, so jargon is spelled correctly at recognition time rather than patched
   up afterwards.
2. **Acronym expansion** — a deterministic dictionary pass rewrites acronyms
   into their definitions.

## Architecture change: CUDA/NeMo → CPU/sherpa-onnx

The original design targeted NVIDIA NeMo cache-aware streaming with per-stream
GPU boosting. That was invalidated when the deployment target was confirmed as
an **Apple Silicon Mac**: NeMo's boosting tree is CUDA/Triton-dependent and has
no Apple Silicon path.

Replacement: **sherpa-onnx** (ONNX Runtime, CPU) with Silero VAD segmentation
and the `parakeet-tdt-0.6b-v2` offline transducer.

Why this is better rather than merely adequate:

| | NeMo plan | sherpa-onnx plan |
|---|---|---|
| Runs on target Mac | No | Yes |
| Dev/prod parity | None (CUDA dev, Mac prod) | Identical on both |
| Biasing | GPU boosting tree | Hotwords context graph |
| Model | FastConformer 114M (VRAM-limited) | Parakeet TDT 0.6B (top-tier English) |

The 6 GB VRAM constraint that forced a small model disappears entirely: the Mac
has 32 GB of unified memory and the model runs on CPU.

**Why offline-with-VAD rather than a streaming model:** the latency budget is
3–5 s and audio is mic-only. Silero VAD cuts speech at natural pauses and each
segment is decoded by a full offline model, which is more accurate than any
streaming model. At the measured real-time factor a segment decodes in a
fraction of its own duration, so this stays inside the budget.

## Fine-tuning: out of scope

Contextual biasing is the standard alternative to fine-tuning for a fixed
vocabulary of 20–50 terms. It needs no labelled audio, no GPU, and terms are
added by editing a YAML file. Fine-tuning is revisited only if the eval harness
shows specific terms failing even when boosted — with evidence, not upfront.

## Components

| File | Responsibility |
|---|---|
| `salm/glossary.py` | Load/validate the term list; serve both stages |
| `salm/expand.py` | Stage 2 deterministic expansion |
| `salm/asr.py` | sherpa-onnx recogniser + hotwords + VAD |
| `salm/audio.py` | Microphone capture |
| `salm/server.py` | FastAPI + WebSocket; transcript persistence |
| `salm/importers/confluence.py` | Confluence export → candidate YAML |
| `eval/` | Biasing on/off measurement |

`glossary/terms.yaml` is the single source of truth for both stages, so the
biasing list and the expansion table cannot drift apart.

## Expansion policy

`first_use` — expand the first mention, leave later ones bare, keeping long
transcripts readable. Applied to finalised segments only, so captions never
flicker between expanded and unexpanded forms.

## Verification

- **Stage 2**: unit tests — word boundaries (`ARR` must not match inside
  `BARRIER`), longest-match precedence, first-use policy, unknown terms
  untouched.
- **Stage 1**: jargon term recall with biasing off vs on, with overall WER as a
  guardrail. Rising WER means the boost score is too high.

## Out of scope

Speaker diarization; multi-user serving/auth; a local LLM for disambiguation;
auto-mining jargon from documents; meeting-bot integration.
