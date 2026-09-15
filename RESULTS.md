# Results

Outcomes against [`HYPOTHESES.md`](HYPOTHESES.md), which was committed before the measurement
code existed. Nothing in the pre-registration was edited after these landed.

**5 held · 2 failed · 2 unresolved.**

| | Hypothesis | Tier | Outcome |
|---|---|---|---|
| H1 | There is no house cut-rate template | confirmatory | **HELD** |
| H2 | The container is fixed even though the interior is not | confirmatory | **HELD** |
| H3 | The frame rate is a deliberate cinema choice | confirmatory | **HELD** |
| H4 | The opening three seconds carry no spoken product name | pre-registered | *inconclusive* |
| H5 | Shot length is front-loaded | pre-registered | **FAILED** |
| H6 | Founders appear on camera in a minority | pre-registered | *inconclusive* |
| H7 | Runtime does not track engagement | pre-registered | **HELD** |
| H8 | Post copy is longer than the fold | pre-registered | **HELD** |
| H9 | The format is stable over time, not converging | pre-registered | **FAILED** |

---

## The headline

**Inside the frame there is no house style. The frame itself barely moves.**

Cut counts run from 0 to 50 across seven videos of comparable length. Cartesia's is a single
unbroken 140-second take; Wispr Flow's cuts fifty times in 157 seconds. Whatever Social Capital
standardises, it is not pacing, shot grammar, or edit density.

What does hold for all seven: 16:9 landscape, a real audio track, 60–200 seconds of runtime.
Five of seven sit at 23.976 fps — the cinema rate. A phone captures at 30 or 60; a 24p timeline
is something a person chose in an edit suite.

That combination runs against the short-form playbook in every direction at once. Landscape,
not vertical. Minutes, not seconds. Sound-on, into feeds that autoplay muted.

## The most useful result is a failed prediction

**H9 failed, and its failure is the finding.**

H9 predicted the format was fixed from the start. It was not. Runtime spread across the four
2025 launches has a coefficient of variation of 0.29; across the three 2026 launches, 0.07.
The 2025 videos run 1:29 to 2:54. The 2026 videos run 2:37 to 3:02.

The container was **converged on**, not imposed. That is what a format being *found* looks
like — and it means the interesting question is not "what is the template" but "what were they
optimising toward between February 2025 and March 2026."

This is also the most fragile result on the page: four points against three, and a coefficient
of variation over three observations moves a long way on one video. It is reported because it
was predicted and it failed, not because the evidence is strong.

## H5 failed on its own bound

4 of 5 measurable videos cut faster in the opening quarter than the closing quarter — the
direction the hypothesis predicted. The pre-registered bound was 5 of 7, and two videos were
excluded as unmeasurable: Cartesia has no cuts at all, and Superblocks has none in its opening
quarter. A video with no cut in a window has no shot length to compare there.

An earlier version of this code compared the two windows anyway. With no cuts, both sides fall
back to the window width, and a floating-point tie-break silently filed Cartesia under "cuts
faster at the open." A test now pins that behaviour
(`test_equal_windows_never_silently_count_as_front_loaded`).

Reporting this as HELD by quietly counting a coin-flip would have been easy and wrong.

## Two hypotheses stayed open

H4 and H6 need speech-to-text and a vision model respectively. No credential was available for
this run. Both measurements are implemented and will close when a key is present; neither is
reported as HELD, and neither was dropped from the list to make the scoreboard tidier.

## A disclosure about H8's bound

H8's pre-registration wrote the threshold as "5/7", conflating *launches with video* (7) with
*hero posts* (9). Every launch has a post; only seven have a video. It is evaluated here
against all nine posts, which is the population the claim was actually about. Noting the slip
rather than silently correcting it.

The result: 8 of 9 hero posts exceed X's 280-character fold, and all nine land inside a
44-character band — 266 to 310. Nine posts, nine founders, nine companies, and a 44-character
spread. The copy is written to a length.

## One thing found by accident

The earliest listed launch, Icon (Feb 2025), belongs to `@kennandavison` — Social Capital's own
co-founder. The first case study on the wall is the house's own company. Nothing follows from
that measurement-wise; it is just the kind of detail that only turns up if you read the data
instead of the deck.

## What would change these answers

- **The amplifier roster.** Who reposts each launch is the question worth answering and it sits
  behind the paid X API. Everything here measures the asset, not the distribution.
- **LinkedIn.** HTTP 999 to unauthenticated requests. Half the network is invisible here.
- **A baseline.** Comparing a launch post against the same founder's ordinary posts would
  separate the network's contribution from the founder's own reach. That needs timeline access.
- **More launches.** n = 7 supports description and nothing else.
