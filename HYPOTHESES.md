# Pre-registered hypotheses

Written and committed **before** the measurement pipeline existed. Nothing below is edited
after results land; outcomes are recorded in `RESULTS.md` and rendered on the site, including
the ones that fail.

## Why this file exists

An analysis you can revise after seeing the data will always look insightful. The only way a
claim about seven videos means anything is if the claim was fixed in advance and the failures
are reported as loudly as the hits.

## Disclosure: two tiers of hypothesis

I ran a scouting probe before writing this file. That probe measured **duration, frame rate,
resolution, audio presence, and scene-cut counts** on all seven videos. Pretending H1–H3 were
formed blind would be false, so they are not claimed as blind.

- **Tier A — confirmatory (post-probe).** The pattern was already visible. These are stated so
  the site can show the numbers behind a claim I had already formed. They are *not* evidence of
  successful prediction, and the site labels them that way.
- **Tier B — pre-registered (blind).** Written before any measurement of that dimension exists.
  The pipeline has not yet been built for any of these. These are real predictions and several
  are expected to fail.

n = 7 launch videos (Airwallex and Deel shipped without one). Seven is too few for a
significance claim, and no p-value appears anywhere in this project. Everything here is
descriptive.

---

## Tier A — confirmatory (post-probe, not blind)

### H1 · There is no house cut-rate template
Cut counts vary by more than an order of magnitude across comparable runtimes, and the ordering
is stable across detection thresholds (0.2 / 0.3 / 0.4).

**Closes as:** HELD / FAILED, by whether max(cuts) / min(cuts) > 10 at every threshold.

### H2 · The container is fixed even though the interior is not
All seven are 16:9 landscape, carry an audio track, and run between 60 and 200 seconds.

**Closes as:** HELD only if all three hold for 7/7. Any single exception fails it.

### H3 · The frame rate is a deliberate cinema choice
A majority run at 23.976 fps — a film-timeline rate, not a phone-capture default (30 / 60).

**Closes as:** HELD if ≥ 4/7 are 23.976, FAILED otherwise.

---

## Tier B — pre-registered (blind, not yet measured)

### H4 · The opening three seconds carry no spoken product name
Prediction: in ≥ 5/7, the product name is not *spoken* in the first 3 seconds of transcript.
Rationale: if these are films rather than ads, they open on premise, not on branding.

### H5 · Shot length is front-loaded
Prediction: in ≥ 5/7, the mean shot length in the first 25% of runtime is *shorter* than in the
final 25% — a fast hook that settles.
Counter-possibility: the reverse (slow open, fast climax) is a normal film grammar and would
fail this cleanly.

### H6 · Founders appear on camera in a minority
Prediction: ≤ 3/7 contain a sustained talking-head shot of the founder.
Rationale: their site sells filmmakers and motion designers, not spokesperson coaching.

### H7 · Runtime does not track engagement
Prediction: |Spearman ρ| < 0.5 between video duration and the hero post's like count.
Explicitly descriptive — n = 7 cannot support an inference either way, and a strong ρ here
would be reported as noise, not as a relationship.

### H8 · Post copy is longer than the fold
Prediction: ≥ 5/7 hero posts exceed the X "Show more" truncation point, meaning the copy is
written to be expanded rather than skimmed.

### H9 · The format is stable over time, not converging
Prediction: format variance across the four launches from 2026 is not lower than across the
three from 2025. If the container were a playbook still being found, later launches would
cluster tighter. If it was fixed from the start, they will not.
Rationale: this is the hypothesis most likely to fail, and the one whose failure would be most
interesting — convergence would mean the format was *learned*, not imposed.

---

## What this project deliberately does not claim

- No causal claim that format drives reach. There is no control group and no counterfactual.
- No amplifier-network reconstruction. That data sits behind the paid X API; anything here
  would be guesswork dressed as measurement.
- No LinkedIn measurement. LinkedIn returns HTTP 999 to unauthenticated requests and nothing
  reliable can be read without an account.
- No engagement modelling. Seven points, wildly different audience sizes, no baseline.
