"""Diagnose a failing enrich run.

    python -m pipeline.doctor

Prints what the API actually offers and the exact error behind a failure. Never prints the key,
and never writes it anywhere.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .groq import BASE, TRANSCRIBE_MODEL, VISION_MODEL, GroqUnavailable, api_key, have_key

ROOT = Path(__file__).resolve().parents[1]


def _get(path: str) -> dict:
    request = urllib.request.Request(
        BASE + path, headers={"Authorization": f"Bearer {api_key()}"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    print("=" * 70)
    print("GROQ DIAGNOSTIC")
    print("=" * 70)

    key = os.environ.get("GROQ_API_KEY", "").strip()
    print(f"key present            : {bool(key)}")
    print(f"key length             : {len(key)}")
    print(f"key looks like a Groq key: {key.startswith('gsk_') if key else False}")
    if not have_key():
        print("\nNo key in this shell. In PowerShell, set it and re-run in the SAME window:")
        print('  $env:GROQ_API_KEY = "gsk_..."')
        return 1

    print(f"\nconfigured transcribe model: {TRANSCRIBE_MODEL}")
    print(f"configured vision model    : {VISION_MODEL}")

    print("\n--- asking the API what it offers ---")
    try:
        models = sorted(m["id"] for m in _get("/models").get("data", []))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")[:300]
        print(f"FAILED to list models: HTTP {error.code} - {body}")
        if error.code == 401:
            print("\n401 means the key was rejected. Regenerate it at console.groq.com.")
        return 1
    except urllib.error.URLError as error:
        print(f"FAILED to reach Groq: {error.reason}")
        return 1

    print(f"{len(models)} models available\n")

    whisper = [m for m in models if "whisper" in m.lower()]
    vision = [m for m in models if any(t in m.lower() for t in ("vision", "llava", "scout", "maverick", "llama-4"))]

    print("speech-to-text candidates:")
    for model in whisper or ["  (none found)"]:
        mark = "  <- configured" if model == TRANSCRIBE_MODEL else ""
        print(f"  {model}{mark}")

    print("\nvision candidates:")
    for model in vision or ["  (none found)"]:
        mark = "  <- configured" if model == VISION_MODEL else ""
        print(f"  {model}{mark}")

    print("\n--- verdict ---")
    ok = True
    if TRANSCRIBE_MODEL not in models:
        ok = False
        print(f"WRONG: transcribe model '{TRANSCRIBE_MODEL}' is not offered.")
        if whisper:
            print(f"       set GROQ_TRANSCRIBE_MODEL to one of: {', '.join(whisper)}")
    else:
        print(f"OK: transcribe model '{TRANSCRIBE_MODEL}' exists.")

    if VISION_MODEL not in models:
        ok = False
        print(f"WRONG: vision model '{VISION_MODEL}' is not offered.")
        if vision:
            print(f"       set GROQ_VISION_MODEL to one of: {', '.join(vision)}")
    else:
        print(f"OK: vision model '{VISION_MODEL}' exists.")

    if not ok:
        print("\nAll models offered, for reference:")
        for model in models:
            print(f"  {model}")

    print("\n--- live call test ---")
    audio = next((ROOT / "data" / "audio").glob("*.mp3"), None) if (ROOT / "data" / "audio").exists() else None
    if audio is None:
        print("no extracted audio yet; run `python -m pipeline.enrich` once to create it")
    else:
        from .groq import transcribe

        try:
            result = transcribe(audio)
            print(f"transcription OK: {(result.get('text') or '')[:80]!r}")
        except GroqUnavailable as error:
            print(f"transcription FAILED: {error}")

    frame = next((ROOT / "site" / "frames").glob("*.jpg"), None)
    if frame is None:
        print("no frames found")
    else:
        from .groq import classify_frames

        try:
            verdict = classify_frames([frame], 'Reply as JSON: {"ok": true}')
            print(f"vision OK: {verdict}")
        except GroqUnavailable as error:
            print(f"vision FAILED: {error}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
