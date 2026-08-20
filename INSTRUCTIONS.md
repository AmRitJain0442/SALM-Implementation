# Note to the Claude setting this up

You're installing SALM on a colleague's Mac. This note is written for you, not
for a human — it covers the setup, the things that will look like bugs but
aren't, and the decisions that are already settled so you don't spend the
session re-deriving them.

**What this is:** local meeting transcription that expands the firm's acronyms.
Audio → Silero VAD → Parakeet TDT (ONNX, CPU) → glossary correction → acronym
expansion → live captions in a browser. Everything runs on the machine; nothing
goes to a cloud API. No GPU, no CUDA, no API keys.

---

## Setup

```bash
git clone https://github.com/AmRitJain0442/SALM-Implementation.git
cd SALM-Implementation
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/setup.py          # ~700 MB of models, once, resumable
python -m salm check
python -m salm serve             # http://127.0.0.1:8000
```

The glossary is committed, so there is nothing to copy across. `salm check`
tells you what's missing and what to run next.

Any Python 3.10+ is fine. `sherpa-onnx` publishes macOS arm64 wheels for
cp38–cp314 and `sounddevice` ships `universal2`, so nothing builds from source.
If pip *does* start compiling something, stop and check which Python is active
rather than waiting it out.

---

## The one Mac problem that actually bites

**macOS asks for microphone permission once and never asks again.** If the
answer was no, or the prompt never appeared, `salm check` reports no input
device and there is nothing in the logs to explain it.

Fix: System Settings → Privacy & Security → Microphone → enable the terminal
app (Terminal, iTerm, or VS Code — whichever is actually running Python), then
**restart that app**. Toggling the switch is not enough; the process reads the
permission at launch.

You can confirm the OS sees a device independently of this project:

```bash
python -c "import sounddevice as sd; print(sd.query_devices(kind='input')['name'])"
```

Don't debug the audio pipeline until that line prints a device name.

---

## Verifying it works, in order

Each step isolates a different layer. Do them in sequence; don't skip to the
microphone.

**1. Everything is present**

```bash
python -m salm check          # expect [ok] on model, VAD, glossary, microphone
```

**2. The code is sound** — 95 tests, ~15s. Some load the real model and decode
real audio, so this also proves the model works.

```bash
python -m pytest tests/ -q
```

**3. The whole pipeline, no microphone needed** — replays sample recordings
through the live path at real-time pace. Open the page and press Start.

```bash
python -m salm serve --demo
```

Demo mode automatically uses `glossary/terms.example.yaml`, because the bundled
recordings contain invented terms. Pass `--glossary` to override.

**4. One recording, end to end.** The sample clips belong to the sample
glossary, so name it explicitly:

```bash
python -m salm transcribe eval/audio/j4.wav --show-raw --glossary glossary/terms.example.yaml
```

Expected:

```
Orbex reconciliation runs before the CRIMS (Client Risk Management System) batch.
    heard: Orbeck's reconciliation runs before the CRIMS batch.
    fixed: Orbeck's -> Orbex (0.73)
```

**5. The measured numbers** — should reproduce exactly. If they don't, something
is wrong with the model or the audio, not the glossary.

```bash
python eval/run_eval.py
```

```
transcription only    12/17 =  71%    14.1%       0
+ correction @ 0.75   17/17 = 100%     4.2%       0
```

**6. Finally, a real microphone.** `python -m salm serve` — no `--demo`, so it
uses the real firm glossary. Press Start and say something like *"the E D and
the R P discussed the P D T A results"*. Expect:

```
The ED (Engagement Director) and the RP (Responsible Partner) discussed
the PDTA (Performance Development Trajectory Assessment) results.
```

Text appears about a second after you stop talking.

---

## Things that look like bugs and are not

**Two glossaries live in the repo, deliberately.** `glossary/terms.yaml` is the
real vocabulary the app uses; `glossary/terms.example.yaml` holds invented terms
and belongs to the sample recordings and the test suite. Tools that work on
sample audio select the sample glossary automatically. Don't "consolidate" them
— the tests would then depend on the real vocabulary and break whenever someone
edits it.

**Correction never fires for most of the firm's acronyms.** Correct. 14 of the
23 terms (`AP`, `ED`, `PD`, `RP`, `DIP`, `GREEN`, `BLUE`, …) are ordinary
English words, and the corrector deliberately refuses to rewrite common words
into jargon. The recogniser already gets them right; the value for this glossary
is *expansion*, not correction. Do not lower the thresholds to "fix" this — it
will start turning `crimes` into `CRIMS`.

**Silence produces "Okay." or "Mm-hmm."** The model hallucinates short
acknowledgements on near-silence. VAD catches most of it and `is_filler()` in
`salm/asr.py` catches the rest. If you see one leak through, add it to
`_FILLERS`; don't touch the VAD thresholds.

**`GREEN` / `BLUE` / `INDIGO` never expand.** Speech produces lowercase
"green"; matching is case-sensitive. This is deliberate — expanding every
"green" would be unreadable.

**`PD` expands to "People development or Professional development".** That "or"
comes from the source glossary and reads badly mid-sentence. It's a content fix
in `glossary/terms.yaml`, not a code fix.

**Beam search is used even with no hotwords.** Intentional — greedy decoding
transcribes "Kubernetes" as "CubaNets" on the same clip. Don't switch it to
greedy for speed; decode is already ~11x faster than real time.

---

## Settled decisions — please don't reopen these

These were decided on measurement, not preference. Each has numbers behind it in
`MEMORY.md`.

**Contextual biasing is off, and should stay off.** It's implemented
(`--biasing`) and it loses on every metric at every setting: recall drops from
71% to 65→53%, WER climbs 14% → 17% → 38% → 84%. There is no useful score. If
the friend asks for "the biasing feature from the plan", show them
`python eval/run_eval.py --biasing`.

**Don't install NVIDIA NeMo.** It was the original design and is a dead end
here: the boosting tree is CUDA/Triton-bound with no Apple Silicon path.

**Don't swap in Whisper.** Parakeet TDT was chosen because it is a transducer
with strong English accuracy and collapses spelled-out acronyms natively
("A S P" → "ASP"), which is exactly this use case.

**Don't add an LLM for acronym disambiguation.** The glossary is small and
mostly unambiguous; a lookup table can't hallucinate and costs nothing. Revisit
only if real transcripts show one acronym meaning two things.

**Don't fine-tune.** Not needed for a vocabulary this size, and it would require
labelled recordings of real meetings.

---

## Adding vocabulary

Edit `glossary/terms.yaml`:

```yaml
  - canonical: QBR
    expansion: Quarterly Business Review
    type: acronym
    spoken_forms: ["Q B R"]      # only for real initialisms

  - canonical: Skylark
    type: jargon                 # spelled correctly, never expanded inline
```

**Terms take effect on the next session — no server restart.** Press Stop, then
Start. A malformed file is reported in the status bar rather than failing
silently.

To import a wiki export:

```bash
python -m salm import-glossary export.md      # or .html
```

It writes `glossary/candidates.yaml` for review and never edits the live
glossary, because a wrong entry silently corrupts every later meeting.

**After adding short acronyms, check for collisions.** Two- and three-letter
acronyms collide with ordinary speech. `eval/run_eval.py` measures the *sample*
corpus (its glossary is pinned in the manifest, so its numbers always
reproduce); to check the real vocabulary, sweep it against the common-word list
directly:

```bash
python -c "
from salm.correct import Corrector, COMMON_WORDS
from salm.glossary import Glossary
c = Corrector(Glossary.load('glossary/terms.yaml'))
bad = [w for w in COMMON_WORDS if c._best_match(w, 1)]
print('ordinary words that would be corrupted:', bad or 'none')
"
```

`none` is the answer you want, and is what it currently reports.

---

## Two rules if you change code

**Never use the real glossary in tests.** `tests/conftest.py` pins them to
`glossary/terms.example.yaml`. The suite once read the live glossary and broke
the moment a real one was installed — tests were passing for machine-specific
reasons.

**Keep test output pristine.** The one real crash in this project's history — the
capture thread dying when a browser tab closed — surfaced as a pytest *warning*,
not a failure. A tolerated warning would have hidden it.

---

## Where the knowledge is

| file | what's in it |
|---|---|
| `README.md` | what it does, measured results, how it works |
| `MEMORY.md` | findings and their evidence; read this before changing the matcher |
| `PLAN.md` | current status and what's outstanding |
| `eval/run_eval.py` | the harness that settles arguments |

`MEMORY.md` is the important one. It records things that cost real time to
learn — `modeling_unit="bpe"` without a vocab **segfaults** the process rather
than raising, BPE tokenization can be reconstructed from token-id merge order,
and why frequency rather than dictionary membership is the right test for
over-correction.

---

## If you're genuinely stuck

Say so rather than guessing. The likeliest causes, in order: microphone
permission (see above), the wrong Python on `PATH`, or models that were
interrupted mid-download — delete `models/` and re-run `python scripts/setup.py`.

The outstanding work is listed in `PLAN.md`. The main one: every number in this
repo comes from **synthetic speech**, not human voices. If your friend records
themselves reading `eval/manifest.yaml`'s sentences and re-runs the harness,
that would be the single most valuable contribution to the project.
