"""Run the whole pipeline: fetch, parse, measure, evaluate, emit.

    python -m pipeline

Everything is cached. The first run touches nine public pages and downloads seven videos; every
run after that is offline and deterministic.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .analyze import evaluate_all
from .fetch import EXPECTED_SLUGS, download_binary, fetch_case, fetch_index
from .parse import parse_case, parse_index, parse_index_labels
from .video import REPORTING_THRESHOLD, extract_frames, measure

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
VIDEOS = ROOT / "data" / "videos"
FRAMES = ROOT / "site" / "frames"
OUT = ROOT / "site" / "data.json"

PREFERRED_RENDITION = "1280x720"
FRAME_STRIP_COUNT = 6


def _frame_times(duration: float, cut_times: list[float]) -> list[float]:
    """Up to six representative stills: evenly spaced cuts, or even spacing if barely any cuts."""
    if len(cut_times) >= FRAME_STRIP_COUNT:
        step = len(cut_times) / FRAME_STRIP_COUNT
        return [cut_times[int(i * step)] + 0.25 for i in range(FRAME_STRIP_COUNT)]
    if cut_times:
        return [t + 0.25 for t in cut_times]
    return [duration * (i + 1) / (FRAME_STRIP_COUNT + 1) for i in range(FRAME_STRIP_COUNT)]


def main() -> None:
    print("fetching index ...")
    index_html = fetch_index(RAW)
    slugs = parse_index(index_html)
    labels = parse_index_labels(index_html)

    missing = set(EXPECTED_SLUGS) - set(slugs)
    if missing:
        print(f"  WARNING: expected slugs absent from index: {sorted(missing)}")
    added = set(slugs) - set(EXPECTED_SLUGS)
    if added:
        print(f"  NOTE: new case studies published since this was written: {sorted(added)}")

    launches: list[dict] = []
    videos: list[dict] = []

    for slug in slugs:
        print(f"  {slug} ...", end=" ", flush=True)
        launch = parse_case(slug, fetch_case(slug, RAW), labels)
        record = launch.to_dict()

        if launch.video is None:
            record["video_metrics"] = None
            launches.append(record)
            print("no video")
            continue

        url = launch.video.mp4_at(PREFERRED_RENDITION) or launch.video.best_mp4()
        if not url:
            record["video_metrics"] = None
            launches.append(record)
            print("no mp4 rendition")
            continue

        path = download_binary(url, VIDEOS / f"{slug}.mp4")
        metrics = measure(path)

        entry = metrics.to_dict()
        entry.update(
            slug=slug,
            company=launch.company,
            campaign_date=launch.campaign_date,
            favorite_count=launch.favorite_count,
            mean_shot_front_quarter=round(metrics.mean_shot_in_window(0.0, 0.25), 3),
            mean_shot_final_quarter=round(metrics.mean_shot_in_window(0.75, 1.0), 3),
            cuts_front_quarter=metrics.cuts_in_window(0.0, 0.25),
            cuts_final_quarter=metrics.cuts_in_window(0.75, 1.0),
            frames=extract_frames(path, _frame_times(metrics.duration_s, metrics.cut_times), FRAMES),
        )

        record["video_metrics"] = entry
        launches.append(record)
        videos.append(entry)
        print(f"{metrics.duration_s:.0f}s, {metrics.cuts} cuts, {metrics.fps} fps")

    transcripts = _load_optional(ROOT / "data" / "transcripts.json")
    vision = _load_optional(ROOT / "data" / "vision.json")

    verdicts = evaluate_all(launches, videos, transcripts, vision)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "https://www.sociallcapital.com/work",
        "counts": {
            "launches": len(launches),
            "with_video": len(videos),
            "without_video": len(launches) - len(videos),
        },
        "cut_detection": {
            "reporting_threshold": REPORTING_THRESHOLD,
            "thresholds_measured": ["0.2", "0.3", "0.4"],
            "method": "ffmpeg scene-change score; counts reported at every threshold",
        },
        "launches": launches,
        "videos": videos,
        "hypotheses": verdicts,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\nwrote {OUT.relative_to(ROOT)}")
    for verdict in verdicts:
        print(f"  {verdict['id']:3} {verdict['outcome']:13} {verdict['claim']}")


def _load_optional(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
