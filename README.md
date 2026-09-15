# The Format Contract

**What nine public Social Capital launches say about the container their videos ship in.**

Social Capital sells three things on its site: research into how the X and LinkedIn algorithms
work, a distribution network worth 300M+ monthly views, and in-house creative — filmmakers,
writers, art directors, motion designers. The obvious assumption is that the network is the
product.

This measures the creative instead, because it is the part that leaves public artifacts.

**The finding: the public launch assets vary inside the frame, while runtime narrows over time.**
At the reporting threshold, detected cut counts run 0 to 50 across seven videos of similar
length. Every one is 16:9 landscape with a real audio track and runs one to three minutes.
Five of seven have a 23.976 fps delivery rate. The three 2026 launch videos sit in a tighter
runtime band than the four from 2025—a descriptive signal that the delivery format may have
been learned rather than imposed.

Full outcomes in [`RESULTS.md`](RESULTS.md). Predictions in
[`HYPOTHESES.md`](HYPOTHESES.md), committed before the measurement code existed.

---

## Why the pre-registration matters more than the finding

Any analysis you can revise after seeing its data will look insightful. Nine hypotheses were
written and committed first; the code that could test them came second. Three of them were
formed after a scouting probe and are labelled **confirmatory** — they are not evidence of
successful prediction, and the site says so where it shows them.

Two blind predictions failed. Both failures are on the page, one of them as the headline.

**4 held · 2 failed · 3 inconclusive.**

Two hypotheses need speech-to-text and a vision model. A third (H1) is inconclusive because
its pre-registered max/min ratio is undefined when a video has zero detected cuts. Rather than
quietly replacing the rule with a different test, the site reports the observed gaps as
descriptive context and leaves the original verdict open.

## Running it

```bash
pip install -r requirements.txt
python -m pipeline
```

The first run makes one polite pass over nine public pages and downloads seven videos, caching
everything to `data/`. Every run after that is offline and deterministic. `ffmpeg` arrives as a
static binary with `imageio-ffmpeg`, so nothing needs installing system-wide.

Two hypotheses (H4, H6) need a speech and a vision model. With a free Groq key:

```bash
export GROQ_API_KEY=...        # never committed; read from the environment only
python -m pipeline.enrich      # writes data/transcripts.json and data/vision.json
python -m pipeline             # re-closes every hypothesis
```

Without the key `enrich` exits cleanly and changes nothing — those two stay `INCONCLUSIVE`,
which is a legitimate outcome rather than a failure.

View the result:

```bash
python -m http.server 8777 --directory site
```

`site/index.html` also opens straight off disk — the pipeline emits the data as both
`data.json` and a `data.js` global, so a `file://` origin does not leave you with a blank page.

## GitHub Pages

GitHub Pages opens the checked-in static artifact in `site/`. It deliberately does **not**
refetch public pages during deployment: the visible result stays tied to the cached source
snapshot committed with it.

## Tests

```bash
python -m pytest
```

83 collected test cases cover the parsers, metric arithmetic, and every hypothesis verdict.
They caught real bugs:

- A max/min spread ratio that clamped a genuine zero to one. The original ratio now remains
  inconclusive rather than being replaced by a post-hoc cutoff.
- A front-loading comparison that let a floating-point tie-break file a video with no cuts
  under "cuts faster at the open."
- A mean-shot calculation that counted cuts rather than the cuts-plus-one shots they create.

Both are pinned by name in `tests/test_analyze.py`.

## How the data is obtained

The case-study pages at `sociallcapital.com/work/<slug>` are server-rendered Next.js. Each one
embeds the launch's X post — via X's own syndication API — inside the RSC flight payload.
`pipeline/flight.py` reconstructs that payload and lifts the post object out: founder, handle,
full copy, timestamp, engagement counts, and direct MP4 URLs at every rendition.

No authentication, no account, no scraping of anything a browser would not already load.
One request per page, cached so re-runs make none.

## Layout

```
HYPOTHESES.md      predictions, committed before the measuring code existed
RESULTS.md         outcomes, including the two that failed
pipeline/
  flight.py        decode the Next.js RSC payload
  fetch.py         cached, rate-limited retrieval
  parse.py         page -> launch record
  video.py         ffmpeg measurement: duration, fps, cuts, shot lengths
  groq.py          stdlib client for speech-to-text and vision (optional)
  enrich.py        produce transcripts.json / vision.json for H4 and H6
  analyze.py       close each hypothesis, with its evidence
  __main__.py      orchestration -> site/data.json
site/              static page; no server, no build step, no dependencies
tests/             83 collected test cases
```

## What this does not claim

No causal claim that format drives reach — there is no control group. No amplifier-network
reconstruction; that needs the paid X API. No LinkedIn measurement; it answers unauthenticated
requests with HTTP 999. And n = 7, which supports description and nothing more. No p-value
appears anywhere in this repository.

---

Built by [Saransh Baid](https://github.com/Saraid10) from public data.
Not affiliated with Social Capital Inc.
