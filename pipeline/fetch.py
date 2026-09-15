"""Fetch and cache the public sociallcapital.com case-study pages.

Every network read is cached to disk on first use. Re-running the pipeline touches the network
zero times, which keeps request volume to one polite pass over nine public pages.
"""

from __future__ import annotations

import time
import urllib.request
from pathlib import Path

BASE = "https://www.sociallcapital.com"
INDEX_PATH = "/work"

# Slugs are read from the index page; this list is the expected set, used only to verify the
# index parse did not silently lose one.
EXPECTED_SLUGS = (
    "playerzero",
    "wispr-flow",
    "poly-ai",
    "airwallex",
    "gamma",
    "cartesia",
    "deel",
    "superblocks",
    "icon",
)

USER_AGENT = "format-contract/1.0 (public-page analysis; contact via github.com/Saraid10)"
DELAY_SECONDS = 1.0


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_cached(url: str, cache_path: Path, delay: float = DELAY_SECONDS) -> str:
    """Return the page text, fetching only if it is not already on disk."""
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="replace")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    body = _get(url)
    cache_path.write_bytes(body)
    time.sleep(delay)
    return body.decode("utf-8", errors="replace")


def fetch_index(cache_dir: Path) -> str:
    return fetch_cached(BASE + INDEX_PATH, cache_dir / "work.html")


def fetch_case(slug: str, cache_dir: Path) -> str:
    return fetch_cached(f"{BASE}{INDEX_PATH}/{slug}", cache_dir / f"{slug}.html")


def download_binary(url: str, dest: Path) -> Path:
    """Download a media file once. Returns the path whether or not it was already present."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_get(url))
    return dest
