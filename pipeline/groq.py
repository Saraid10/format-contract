"""Minimal Groq client over the standard library.

The rest of this project has no runtime dependencies beyond ffmpeg, and adding an SDK to make
two kinds of call would not earn its place. Both endpoints are OpenAI-compatible.

The key is read from the GROQ_API_KEY environment variable and is never written to disk, never
logged, and never included in any emitted artifact.
"""

from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = "https://api.groq.com/openai/v1"

# Model ids are configurable because providers retire them; the defaults are what these
# endpoints expect today, and a wrong id fails loudly rather than silently degrading.
TRANSCRIBE_MODEL = os.environ.get("GROQ_TRANSCRIBE_MODEL", "whisper-large-v3")
VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")


class GroqUnavailable(RuntimeError):
    """Raised when no key is configured, or the API refuses the request."""


def api_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise GroqUnavailable("GROQ_API_KEY is not set")
    return key


def have_key() -> bool:
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def _post(url: str, body: bytes, content_type: str) -> dict:
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": content_type},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        # The key itself is never part of the message.
        raise GroqUnavailable(f"HTTP {error.code} from {url.rsplit('/', 1)[-1]}: {detail}") from None
    except urllib.error.URLError as error:
        raise GroqUnavailable(f"could not reach Groq: {error.reason}") from None


def transcribe(audio_path: Path) -> dict:
    """Transcribe with word-level timestamps so an opening window can be sliced exactly."""
    boundary = f"----format-contract-{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"

    fields = [
        ("model", TRANSCRIBE_MODEL),
        ("response_format", "verbose_json"),
        ("timestamp_granularities[]", "word"),
        ("timestamp_granularities[]", "segment"),
    ]

    parts: list[bytes] = []
    for name, value in fields:
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{audio_path.name}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
    )
    parts.append(audio_path.read_bytes())
    parts.append(f"\r\n--{boundary}--\r\n".encode())

    return _post(
        f"{BASE}/audio/transcriptions",
        b"".join(parts),
        f"multipart/form-data; boundary={boundary}",
    )


def classify_frames(image_paths: list[Path], prompt: str) -> dict:
    """Ask the vision model one question about a handful of frames. Returns parsed JSON."""
    import base64

    content: list[dict] = [{"type": "text", "text": prompt}]
    for path in image_paths:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}
        )

    payload = {
        "model": VISION_MODEL,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    response = _post(f"{BASE}/chat/completions", json.dumps(payload).encode(), "application/json")
    text = response["choices"][0]["message"]["content"]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise GroqUnavailable(f"model did not return JSON: {text[:200]}") from None
