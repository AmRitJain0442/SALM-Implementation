# Demo script

Five sentences, verified end to end through the real pipeline against
`glossary/terms.yaml`. Say them in this order — the last one only works if the
earlier ones came first.

Start with `python -m salm serve`, open http://127.0.0.1:8000, press **Start
listening**, then pause about a second between sentences so the voice detector
cuts cleanly.

---

## The script

> **1.** "The A-S-P signed off on the E-P-R last week."
>
> **2.** "The E-D and the R-P discussed the P-D-T-A results."
>
> **3.** "Please send the C-I-R to the E-C before Friday."
>
> **4.** "The D-G-L reviewed all the D-R-O cases this quarter."
>
> **5.** "I'll resend the P-D-T-A to the E-D tomorrow."

## What appears on screen

```
1. The ASP (Accountable Senior Partner) signed off on the
   EPR (Engagement Performance Review) last week.

2. The ED (Engagement Director) and the RP (Responsible Partner) discussed
   the PDTA (Performance Development Trajectory Assessment) results.

3. Please send the CIR (Collaborator Input Report) to the
   EC (Engagement Contact) before Friday.

4. The DGL (Development Group Leader) reviewed all the
   DRO (Development Review Only) cases this quarter.

5. I will resend the PDTA to the ED tomorrow.
```

**Sentence 5 is the one to point at.** `PDTA` and `ED` stay bare because they
were already expanded earlier — expansion happens on first use per session, so
a long transcript doesn't repeat itself. It looks like a bug until you explain
it, so explain it first.

The side panel fills in as you go: every term that fired, with its definition,
and a count.

---

## Speaking notes

- **Say the letters separately** — "ee-dee", not "Ed". The recogniser handles
  spelled-out acronyms well, but a run-together acronym is just a word.
- **Pause about a second between sentences.** Voice detection cuts on silence;
  running sentences together makes one long segment and delays the text.
- Text appears roughly a second after you stop talking. If it takes longer, the
  machine is busy — it is not waiting on anything remote.

---

## Spare sentences

All verified individually. Useful if someone asks for more, or if you want to
introduce different terms.

> "Her A-E-D is next month, so the P-D should be looped in."
>
> "The D-I-P shows every C-S-P survey response."
>
> "The E-A will forward the E-P-R to the E-D."
>
> "Both the A-P and the A-S-P are attending the review."
>
> "We need the T-L to confirm before the C-I-R goes out."

---

## Two things to avoid on stage

**Don't say "the E-S-P one is still open."** The recogniser merges the trailing
"one" into the acronym and writes `ESP1`, which then doesn't expand. Any
acronym followed by a spoken number has this problem — say "the E-S-P survey"
instead.

**Don't demo `GREEN`, `BLUE`, `INDIGO` or `ROY`.** They're in the glossary but
won't expand: speech produces lowercase "green", and matching is
case-sensitive. That is deliberate — expanding every "green" would make
transcripts unreadable — but it is not a good look mid-demo.

---

## If you want to show the repair feature too

The firm's acronyms are recognised correctly, so nothing needs repairing and
the **Repairs** panel stays empty. To show correction actually working, run the
sample glossary instead:

```bash
python -m salm serve --demo
```

Press Start and it replays recordings that contain deliberately awkward jargon.
You'll see `Orbeck's` struck through beside `Orbex`, which is the clearest
illustration of what the correction stage does.

---

## Caveat

These were verified with synthetic speech, not a human voice. The acronyms are
spelled-out letters, which the model handles reliably, so they should transfer —
but **run through the script once before the demo** rather than trusting this
page.
