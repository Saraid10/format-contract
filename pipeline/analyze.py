"""Close each pre-registered hypothesis against the measurements.

Every hypothesis returns HELD, FAILED or INCONCLUSIVE together with the numbers behind the
verdict. A hypothesis that cannot be evaluated says why rather than quietly disappearing, and
INCONCLUSIVE is never used to soften a result that did resolve.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

HELD = "HELD"
FAILED = "FAILED"
INCONCLUSIVE = "INCONCLUSIVE"

TIER_A = "confirmatory"
TIER_B = "pre-registered"

CONTAINER_MIN_S = 60.0
CONTAINER_MAX_S = 200.0


@dataclass
class Verdict:
    id: str
    tier: str
    claim: str
    outcome: str
    detail: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation. Returns None when there is no variance to correlate."""
    n = len(xs)
    if n < 3 or len(ys) != n:
        return None

    def rank(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            shared = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[order[k]] = shared
            i = j + 1
        return ranks

    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def _cv(values: list[float]) -> float | None:
    """Coefficient of variation — a scale-free spread measure for comparing cohorts."""
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    if mean == 0:
        return None
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return (variance**0.5) / abs(mean)


def h1_no_cut_template(videos: list[dict]) -> Verdict:
    """Evaluate H1 exactly as it was written before video measurement.

    H1's original max/min rule becomes undefined if a threshold yields a zero cut count.
    A gap is still useful descriptive context, but it must not silently replace the original
    decision rule or turn an untestable ratio into a HELD result.
    """
    spread: dict[str, dict[str, int]] = {}
    orderings: list[tuple[str, ...]] = []

    for threshold in ("0.2", "0.3", "0.4"):
        counts = {v["slug"]: v["cut_counts"].get(threshold, 0) for v in videos}
        spread[threshold] = {
            "min": min(counts.values()),
            "max": max(counts.values()),
            "gap": max(counts.values()) - min(counts.values()),
        }
        orderings.append(tuple(sorted(counts, key=lambda s: counts[s])))

    rank_stable = len(set(orderings)) == 1
    undefined = [threshold for threshold, values in spread.items() if values["min"] == 0]
    ratios = {
        threshold: values["max"] / values["min"]
        for threshold, values in spread.items()
        if values["min"] > 0
    }

    if undefined:
        outcome = INCONCLUSIVE
        detail = (
            "H1's pre-registered max/min rule is undefined at "
            f"threshold(s) {', '.join(undefined)} because a video has zero detected cuts. "
            "The large gaps are reported as descriptive evidence, not a substitute verdict."
        )
    else:
        holds = all(ratio > 10 for ratio in ratios.values())
        outcome = HELD if holds else FAILED
        detail = (
            "The pre-registered max/min ratio exceeds 10 at every detection threshold."
            if holds
            else "The pre-registered max/min ratio does not exceed 10 at every threshold."
        )

    return Verdict(
        id="H1",
        tier=TIER_A,
        claim="There is no house cut-rate template",
        outcome=outcome,
        detail=detail,
        evidence={
            "spread_by_threshold": spread,
            "cuts_at_0.3": {v["slug"]: v["cut_counts"].get("0.3", 0) for v in videos},
            "rank_stable_across_thresholds": rank_stable,
            "pre_registered_ratio_by_threshold": ratios,
            "undefined_ratio_thresholds": undefined,
            "descriptive_gap_note": "Absolute gaps are descriptive context only; H1 was registered as a ratio.",
        },
    )


def h2_fixed_container(videos: list[dict]) -> Verdict:
    landscape = [v["slug"] for v in videos if not v["is_landscape"]]
    silent = [v["slug"] for v in videos if not v["has_audio"]]
    out_of_band = [
        v["slug"] for v in videos if not (CONTAINER_MIN_S <= v["duration_s"] <= CONTAINER_MAX_S)
    ]
    holds = not (landscape or silent or out_of_band)

    return Verdict(
        id="H2",
        tier=TIER_A,
        claim="The container is fixed even though the interior is not",
        outcome=HELD if holds else FAILED,
        detail=(
            f"All {len(videos)} are 16:9 landscape, carry audio, and run "
            f"{CONTAINER_MIN_S:.0f}-{CONTAINER_MAX_S:.0f}s."
            if holds
            else f"Exceptions - vertical: {landscape}, silent: {silent}, out of band: {out_of_band}"
        ),
        evidence={
            "n": len(videos),
            "durations_s": {v["slug"]: v["duration_s"] for v in videos},
            "all_landscape": not landscape,
            "all_have_audio": not silent,
            "exceptions": {"vertical": landscape, "silent": silent, "out_of_band": out_of_band},
        },
    )


def h3_cinema_fps(videos: list[dict]) -> Verdict:
    cinema = [v["slug"] for v in videos if v["is_cinema_fps"]]
    holds = len(cinema) >= 4

    return Verdict(
        id="H3",
        tier=TIER_A,
        claim="A majority use a 24p delivery rate",
        outcome=HELD if holds else FAILED,
        detail=(
            f"{len(cinema)} of {len(videos)} have a 23.976/24 fps delivery rate. "
            "This records the exported media property; it does not establish the production process."
        ),
        evidence={
            "cinema_fps": cinema,
            "fps_by_slug": {v["slug"]: v["fps"] for v in videos},
            "threshold": "4 of 7",
        },
    )


def h4_no_spoken_name_in_open(videos: list[dict], transcripts: dict[str, Any]) -> Verdict:
    if not transcripts:
        return Verdict(
            id="H4",
            tier=TIER_B,
            claim="The opening three seconds carry no spoken product name",
            outcome=INCONCLUSIVE,
            detail=(
                "Not evaluated: no speech-to-text credential was available to this run. "
                "The measurement is implemented and will close the moment a key is present."
            ),
            evidence={"transcribed": 0, "required": len(videos)},
        )

    clean: list[str] = []
    named: list[str] = []
    for video in videos:
        entry = transcripts.get(video["slug"])
        if not entry:
            continue
        opening = (entry.get("opening_3s") or "").lower()
        company = (video.get("company") or "").lower()
        token = company.split()[0] if company else ""
        (named if token and token in opening else clean).append(video["slug"])

    evaluated = len(clean) + len(named)
    if evaluated < len(videos):
        outcome = INCONCLUSIVE
    else:
        outcome = HELD if len(clean) >= 5 else FAILED

    return Verdict(
        id="H4",
        tier=TIER_B,
        claim="The opening three seconds carry no spoken product name",
        outcome=outcome,
        detail=f"{len(clean)} of {evaluated} open without speaking the product name.",
        evidence={"opens_clean": clean, "names_product": named, "evaluated": evaluated},
    )


def h5_front_loaded(videos: list[dict]) -> Verdict:
    """A video needs a cut in both windows before its two windows can be compared.

    Without that, `mean_shot_in_window` returns the window width on both sides and the
    comparison degenerates into a floating-point tie-break. Those videos are excluded and
    named, not silently assigned to whichever side rounding favours.
    """
    faster_open: list[str] = []
    slower_open: list[str] = []
    excluded: dict[str, str] = {}
    per_slug: dict[str, dict[str, float]] = {}

    for video in videos:
        slug = video["slug"]
        front = video.get("mean_shot_front_quarter")
        back = video.get("mean_shot_final_quarter")
        front_cuts = video.get("cuts_front_quarter", 0)
        back_cuts = video.get("cuts_final_quarter", 0)

        if front is None or back is None:
            excluded[slug] = "window means unavailable"
            continue
        if front_cuts < 1 or back_cuts < 1:
            excluded[slug] = f"no cut in one window (front={front_cuts}, final={back_cuts})"
            continue

        per_slug[slug] = {"front": round(front, 2), "back": round(back, 2)}
        (faster_open if front < back else slower_open).append(slug)

    evaluated = len(per_slug)
    holds = evaluated > 0 and len(faster_open) >= 5

    return Verdict(
        id="H5",
        tier=TIER_B,
        claim="Shot length is front-loaded",
        outcome=HELD if holds else FAILED,
        detail=(
            f"{len(faster_open)} of {evaluated} measurable videos cut faster in the opening "
            f"quarter than in the closing quarter; the prediction needed 5. "
            f"{len(excluded)} excluded as unmeasurable."
        ),
        evidence={
            "faster_open": faster_open,
            "slower_open": slower_open,
            "excluded": excluded,
            "evaluated": evaluated,
            "threshold": "5 of 7",
            "mean_shot_s": per_slug,
        },
    )


def h6_founders_rarely_on_camera(videos: list[dict], vision: dict[str, Any]) -> Verdict:
    if not vision:
        return Verdict(
            id="H6",
            tier=TIER_B,
            claim="Founders appear on camera in a minority",
            outcome=INCONCLUSIVE,
            detail=(
                "Not evaluated: no vision-model credential was available to this run. "
                "Guessing from filenames or post copy would be assertion, not measurement."
            ),
            evidence={"classified": 0, "required": len(videos)},
        )

    if len(vision) < len(videos):
        return Verdict(
            id="H6",
            tier=TIER_B,
            claim="Founders appear on camera in a minority",
            outcome=INCONCLUSIVE,
            detail=(
                f"Only {len(vision)} of {len(videos)} videos were classified. A partial pass "
                "cannot close a claim about all seven."
            ),
            evidence={"classified": len(vision), "required": len(videos)},
        )

    on_camera = [slug for slug, data in vision.items() if data.get("founder_on_camera")]
    holds = len(on_camera) <= 3

    return Verdict(
        id="H6",
        tier=TIER_B,
        claim="Founders appear on camera in a minority",
        outcome=HELD if holds else FAILED,
        detail=(
            f"{len(on_camera)} of {len(vision)} contain a sustained shot of a person addressing "
            "camera. Read this as a talking-head count, not a founder count - see the caveat."
        ),
        evidence={
            "on_camera": on_camera,
            "classified": len(vision),
            "sampled_frames_only": True,
            "identity_caveat": (
                "A vision model can see that someone is addressing camera; it cannot confirm "
                "that person is the founder. H6 was written as a claim about founders and is "
                "answered here by a weaker proxy. Treat it as directional, not settled."
            ),
            "detection_caveat": (
                "Classification runs on frames sampled at cut points, not the full video, so a "
                "talking-head shot that falls entirely between sampled frames is missed."
            ),
        },
    )


def h7_runtime_not_engagement(videos: list[dict]) -> Verdict:
    pairs = [
        (v["duration_s"], v["favorite_count"])
        for v in videos
        if v.get("favorite_count") is not None
    ]
    rho = _spearman([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) >= 3 else None

    if rho is None:
        outcome, detail = INCONCLUSIVE, "Too few paired points to rank-correlate."
    elif abs(rho) < 0.5:
        outcome = HELD
        detail = f"Spearman rho = {rho:.2f}. No monotonic relationship at n={len(pairs)}."
    else:
        outcome = FAILED
        detail = (
            f"Spearman rho = {rho:.2f}, above the 0.5 bound. Reported as noise, not a "
            f"relationship: n={len(pairs)} cannot support an inference either way."
        )

    return Verdict(
        id="H7",
        tier=TIER_B,
        claim="Runtime does not track engagement",
        outcome=outcome,
        detail=detail,
        evidence={"n": len(pairs), "spearman_rho": round(rho, 3) if rho is not None else None},
    )


def h8_copy_exceeds_fold(launches: list[dict]) -> Verdict:
    # H8 was registered as 5/7—the seven launches that shipped with a video.  Retain that
    # denominator for its verdict, while exposing the full wall as an exploratory comparison.
    video_launches = [l for l in launches if l.get("video_metrics") is not None]
    if not video_launches:  # Makes the helper usable with minimal synthetic fixtures.
        video_launches = launches
    over = [l["slug"] for l in video_launches if l["exceeds_fold"]]
    all_over = [l["slug"] for l in launches if l["exceeds_fold"]]
    lengths = {l["slug"]: l["post_chars"] for l in launches}
    holds = len(over) >= 5

    return Verdict(
        id="H8",
        tier=TIER_B,
        claim="Post copy is longer than the fold",
        outcome=HELD if holds else FAILED,
        detail=(
            f"{len(over)} of {len(video_launches)} video-launch hero posts pass the original "
            "5/7, 280-character threshold. "
            f"Exploratory full-wall count: {len(all_over)} of {len(launches)}."
        ),
        evidence={
            "over_fold_video_launches": over,
            "over_fold_all_launches": all_over,
            "post_chars": lengths,
            "band": [min(lengths.values()), max(lengths.values())],
            "note": (
                "The original 5/7 denominator is used for the verdict. The 9-post count is "
                "reported separately as exploratory context."
            ),
        },
    )


def h9_format_stable_not_converging(videos: list[dict]) -> Verdict:
    early = [v for v in videos if (v.get("campaign_date") or "").endswith("2025")]
    late = [v for v in videos if (v.get("campaign_date") or "").endswith("2026")]

    if len(early) < 2 or len(late) < 2:
        return Verdict(
            id="H9",
            tier=TIER_B,
            claim="Launch runtime is stable over time, not converging",
            outcome=INCONCLUSIVE,
            detail=f"Cohorts too small to compare spread: {len(early)} in 2025, {len(late)} in 2026.",
            evidence={"n_2025": len(early), "n_2026": len(late)},
        )

    cv_early = _cv([v["duration_s"] for v in early])
    cv_late = _cv([v["duration_s"] for v in late])

    if cv_early is None or cv_late is None:
        outcome, detail = INCONCLUSIVE, "Duration spread could not be computed for both cohorts."
    elif cv_late < cv_early * 0.5:
        outcome = FAILED
        detail = (
            f"2026 duration spread (CV {cv_late:.2f}) is less than half 2025's "
            f"({cv_early:.2f}) - the format looks learned rather than imposed."
        )
    else:
        outcome = HELD
        detail = (
            f"Duration spread did not collapse: CV {cv_early:.2f} in 2025 vs {cv_late:.2f} "
            "in 2026."
        )

    return Verdict(
        id="H9",
        tier=TIER_B,
        claim="Launch runtime is stable over time, not converging",
        outcome=outcome,
        detail=detail,
        evidence={
            "cv_duration_2025": round(cv_early, 3) if cv_early else None,
            "cv_duration_2026": round(cv_late, 3) if cv_late else None,
            "n_2025": len(early),
            "n_2026": len(late),
        },
    )


def evaluate_all(
    launches: list[dict],
    videos: list[dict],
    transcripts: dict[str, Any] | None = None,
    vision: dict[str, Any] | None = None,
) -> list[dict]:
    verdicts = [
        h1_no_cut_template(videos),
        h2_fixed_container(videos),
        h3_cinema_fps(videos),
        h4_no_spoken_name_in_open(videos, transcripts or {}),
        h5_front_loaded(videos),
        h6_founders_rarely_on_camera(videos, vision or {}),
        h7_runtime_not_engagement(videos),
        h8_copy_exceeds_fold(launches),
        h9_format_stable_not_converging(videos),
    ]
    return [v.to_dict() for v in verdicts]
