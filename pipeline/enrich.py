"""Produce the two model-derived inputs that H4 and H6 need.

    python -m pipeline.enrich

Writes `data/transcripts.json` and `data/vision.json`, then re-running `python -m pipeline`
closes both hypotheses. Without GROQ_API_KEY this exits cleanly and changes nothing — the
hypotheses stay INCONCLUSIVE, which is a legitimate outcome rather than a failure state.

Results are cached per launch, so an interrupted run resumes instead of re-spending quota.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .groq import GroqUnavailable, classify_frames, have_key, transcribe
from .video import extract_audio

ROOT = Path(__file__).resolve().parents[1]
VIDEOS = ROOT / "data" / "videos"
AUDIO = ROOT / "data" / "audio"
FRAMES = ROOT / "site" / "frames"
DATA = ROOT / "site" / "data.json"
TRANSCRIPTS = ROOT / "data" / "transcripts.json"
VISION = ROOT / "data" / "vision.json"

OPENING_WINDOW_S = 3.0

# H6 asks whether the founder appears. A vision model can see a person addressing camera; it
# cannot confirm who that person is. The prompt therefore asks only what is observable, and
# `identity_verified: false` is recorded on every result so the limit travels with the data.
VISION_PROMPT = (
    "These are still frames sampled at cut points from a single product launch video, in order.\n"
    "Answer only from what is visible.\n\n"
    'Reply as JSON: {"talking_head": true|false, "shots_with_person_to_camera": <int>, '
    '"note": "<one short sentence>"}\n\n'
    '"talking_head" is true only if at least one frame shows a person facing and addressing the '
    "camera directly, framed from roughly the chest up, as in an interview or piece to camera. "
    "People appearing incidentally, in b-roll, in screen recordings, or in group shots do not "
    "count."
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _opening_text(result: dict, window: float = OPENING_WINDOW_S) -> str:
    """Words spoken before `window` seconds, preferring word timestamps over segments."""
    words = result.get("words") or []
    if words:
        return " ".join(
            w.get("word", "") for w in words if float(w.get("start", 9e9)) < window
        ).strip()

    segments = result.get("segments") or []
    if segments:
        return " ".join(
            s.get("text", "") for s in segments if float(s.get("start", 9e9)) < window
        ).strip()

    # No timestamps at all: refuse to guess by slicing characters off the full transcript.
    return ""


def run() -> int:
    if not have_key():
        print("GROQ_API_KEY is not set. Nothing written; H4 and H6 stay INCONCLUSIVE.")
        print("Set it, then re-run:  python -m pipeline.enrich && python -m pipeline")
        return 0

    if not DATA.exists():
        print("site/data.json missing. Run `python -m pipeline` first.")
        return 1

    slugs = [v["slug"] for v in json.loads(DATA.read_text(encoding="utf-8"))["videos"]]
    transcripts, vision = _load(TRANSCRIPTS), _load(VISION)
    failures = 0

    for slug in slugs:
        video = VIDEOS / f"{slug}.mp4"
        if not video.exists():
            print(f"  {slug}: video absent, skipped")
            continue

        if slug in transcripts:
            print(f"  {slug}: transcript cached")
        else:
            try:
                audio = extract_audio(video, AUDIO / f"{slug}.mp3")
                result = transcribe(audio)
                opening = _opening_text(result)
                transcripts[slug] = {
                    "opening_3s": opening,
                    "full_text": (result.get("text") or "").strip(),
                    "had_word_timestamps": bool(result.get("words")),
                }
                _save(TRANSCRIPTS, transcripts)
                print(f"  {slug}: opening 3s -> {opening[:64]!r}")
            except GroqUnavailable as error:
                failures += 1
                print(f"  {slug}: transcription failed - {error}")

        if slug in vision:
            print(f"  {slug}: frames cached")
            continue

        frames = sorted(FRAMES.glob(f"{slug}-*.jpg"))
        if not frames:
            print(f"  {slug}: no frames to classify")
            continue
        try:
            verdict = classify_frames(frames[:5], VISION_PROMPT)
            vision[slug] = {
                "founder_on_camera": bool(verdict.get("talking_head")),
                "shots_with_person_to_camera": verdict.get("shots_with_person_to_camera"),
                "note": verdict.get("note", ""),
                "frames_examined": len(frames[:5]),
                # The model sees a person to camera; it cannot confirm that person is the founder.
                "identity_verified": False,
            }
            _save(VISION, vision)
            print(f"  {slug}: talking head -> {vision[slug]['founder_on_camera']}")
        except GroqUnavailable as error:
            failures += 1
            print(f"  {slug}: vision failed - {error}")

    print(f"\ntranscripts: {len(transcripts)}/{len(slugs)}   vision: {len(vision)}/{len(slugs)}")
    if failures:
        print(f"{failures} call(s) failed. Partial coverage keeps the hypothesis INCONCLUSIVE.")
    print("Now re-run:  python -m pipeline")
    return 0


if __name__ == "__main__":
    sys.exit(run())
