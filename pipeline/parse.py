"""Turn a case-study page into a structured launch record."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from .flight import decode_flight, extract_json_object

# X "Show more" truncates the visible post body at this many characters. Used by H8.
FOLD_CHARS = 280

_SLUG_RE = re.compile(r'"(/work/[a-z0-9-]+)"')
_LABEL_RE = re.compile(r"([A-Z][A-Za-z0-9 .]*?)\s+((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+20\d{2})")


@dataclass
class VideoRef:
    video_id: str
    duration_ms: int | None
    aspect_ratio: list[int] | None
    view_count: int | None
    poster: str | None
    mp4_variants: dict[str, str] = field(default_factory=dict)

    def best_mp4(self) -> str | None:
        """Highest resolution mp4 available, by pixel width parsed from the URL path."""
        if not self.mp4_variants:
            return None
        return max(self.mp4_variants.items(), key=lambda kv: _width_of(kv[0]))[1]

    def mp4_at(self, label: str) -> str | None:
        return self.mp4_variants.get(label)


@dataclass
class Launch:
    slug: str
    company: str | None
    campaign_date: str | None
    founder_name: str | None
    founder_handle: str | None
    post_id: str | None
    post_url: str | None
    posted_at: str | None
    post_text: str
    favorite_count: int | None
    conversation_count: int | None
    video: VideoRef | None

    @property
    def post_chars(self) -> int:
        return len(self.post_text)

    @property
    def exceeds_fold(self) -> bool:
        return self.post_chars > FOLD_CHARS

    def to_dict(self) -> dict:
        data = asdict(self)
        data["post_chars"] = self.post_chars
        data["exceeds_fold"] = self.exceeds_fold
        return data


def _width_of(label: str) -> int:
    match = re.match(r"(\d+)x(\d+)", label)
    return int(match.group(1)) if match else 0


def parse_index(html: str) -> list[str]:
    """Slugs of every case study linked from /work, in page order, deduplicated."""
    seen: list[str] = []
    for path in _SLUG_RE.findall(html):
        slug = path.rsplit("/", 1)[-1]
        if slug and slug not in seen:
            seen.append(slug)
    return seen


def parse_index_labels(html: str) -> dict[str, str]:
    """Map company label -> campaign month, read from the visible index text."""
    text = re.sub(r"<[^>]*>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return {name.strip(): date.strip() for name, date in _LABEL_RE.findall(text)}


def _video_from(obj: dict) -> VideoRef | None:
    video = obj.get("video")
    if not video:
        return None

    variants: dict[str, str] = {}
    for variant in video.get("variants", []):
        src = variant.get("src", "")
        if variant.get("type") != "video/mp4" or not src:
            continue
        match = re.search(r"/(\d+x\d+)/", src)
        if match:
            variants[match.group(1)] = src

    return VideoRef(
        video_id=str(video.get("videoId") or ""),
        duration_ms=video.get("durationMs"),
        aspect_ratio=video.get("aspectRatio"),
        view_count=video.get("viewCount"),
        poster=video.get("poster"),
        mp4_variants=variants,
    )


def _full_text(obj: dict) -> str:
    """Prefer the expanded note_tweet body when the post is long-form."""
    note = obj.get("note_tweet") or {}
    result = (note.get("note_tweet_results") or {}).get("result") or {}
    if result.get("text"):
        return result["text"]
    return obj.get("text") or ""


def parse_case(slug: str, html: str, labels: dict[str, str] | None = None) -> Launch:
    flight = decode_flight(html)
    obj = extract_json_object(flight, "favorite_count") or {}
    user = obj.get("user") or {}
    labels = labels or {}

    handle = user.get("screen_name")
    post_id = obj.get("id_str")
    company = _company_for(slug, labels)

    return Launch(
        slug=slug,
        company=company,
        campaign_date=labels.get(company) if company else None,
        founder_name=user.get("name"),
        founder_handle=handle,
        post_id=post_id,
        post_url=f"https://x.com/{handle}/status/{post_id}" if handle and post_id else None,
        posted_at=_iso(obj.get("created_at")),
        post_text=_full_text(obj),
        favorite_count=obj.get("favorite_count"),
        conversation_count=obj.get("conversation_count"),
        video=_video_from(obj),
    )


def _company_for(slug: str, labels: dict[str, str]) -> str | None:
    """Match a slug to its index label without hardcoding a company list."""
    normalised = slug.replace("-", "")
    for label in labels:
        if label.replace(" ", "").replace("-", "").lower() == normalised:
            return label
    return None


def _iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone(timezone.utc).isoformat()
