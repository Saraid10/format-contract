"""Decode the Next.js RSC flight payload embedded in a sociallcapital.com page.

The case-study pages server-render the X post via the syndication API and inline the
resulting JSON inside `self.__next_f.push([1,"..."])` string chunks. Each chunk is a valid
JSON string literal, so concatenating the decoded chunks reconstructs the flight stream and
the tweet object inside it.
"""

from __future__ import annotations

import json
import re

_PUSH = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')


def decode_flight(html: str) -> str:
    """Concatenate every decoded RSC chunk into one string."""
    chunks = []
    for literal in _PUSH.findall(html):
        try:
            chunks.append(json.loads(literal))
        except json.JSONDecodeError:
            # A truncated or non-conforming chunk is skipped rather than failing the page;
            # the tweet object has never spanned a chunk boundary in practice.
            continue
    return "".join(chunks)


def extract_json_object(text: str, anchor: str) -> dict | None:
    """Return the smallest well-formed JSON object in `text` containing `anchor`.

    Walks left from the anchor to a candidate `{`, then brace-matches forward. Candidates are
    tried outward-in because the tweet object is nested inside larger structures.
    """
    idx = text.find(anchor)
    if idx == -1:
        return None

    starts = [m.start() for m in re.finditer(r"\{", text[:idx])]
    for start in reversed(starts):
        obj = _match_object(text, start)
        if obj is None:
            continue
        if obj.find(anchor) != -1:
            try:
                return json.loads(obj)
            except json.JSONDecodeError:
                continue
    return None


def _match_object(text: str, start: int) -> str | None:
    """Brace-match a JSON object starting at `start`, respecting strings and escapes."""
    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None
