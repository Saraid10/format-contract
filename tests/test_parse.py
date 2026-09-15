"""Parser tests.

These run against a fixture built from the real cached page, so a change in how
sociallcapital.com embeds its data fails the suite instead of silently emitting nulls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.flight import decode_flight, extract_json_object
from pipeline.parse import (
    FOLD_CHARS,
    parse_case,
    parse_index,
    parse_index_labels,
    VideoRef,
)

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

pytestmark = pytest.mark.skipif(
    not (RAW / "work.html").exists(),
    reason="cached pages absent; run `python -m pipeline` once to populate data/raw",
)


def _read(name: str) -> str:
    return (RAW / name).read_text(encoding="utf-8", errors="replace")


def test_index_lists_nine_case_studies() -> None:
    slugs = parse_index(_read("work.html"))
    assert len(slugs) == 9
    assert len(set(slugs)) == 9, "slugs must be deduplicated"
    assert "playerzero" in slugs


def test_index_labels_pair_company_with_month() -> None:
    labels = parse_index_labels(_read("work.html"))
    assert labels["PlayerZero"] == "Mar 2026"
    assert labels["Icon"] == "Feb 2025"
    assert len(labels) == 9


def test_case_parse_extracts_the_hero_post() -> None:
    launch = parse_case("playerzero", _read("playerzero.html"), parse_index_labels(_read("work.html")))
    assert launch.founder_handle == "akoratana"
    assert launch.post_id == "2036111467016319074"
    assert launch.post_url == "https://x.com/akoratana/status/2036111467016319074"
    assert launch.posted_at.startswith("2026-03-23T16:02:57")
    assert launch.favorite_count == 5268
    assert launch.company == "PlayerZero"
    assert launch.campaign_date == "Mar 2026"


def test_every_case_yields_a_founder_and_a_post() -> None:
    labels = parse_index_labels(_read("work.html"))
    for slug in parse_index(_read("work.html")):
        launch = parse_case(slug, _read(f"{slug}.html"), labels)
        assert launch.founder_handle, f"{slug} lost its handle"
        assert launch.post_id, f"{slug} lost its post id"
        assert launch.post_text, f"{slug} lost its copy"
        assert launch.company, f"{slug} did not match an index label"


def test_launches_without_video_are_represented_not_dropped() -> None:
    """Airwallex and Deel shipped without a video. Absent must be None, never a fake zero."""
    labels = parse_index_labels(_read("work.html"))
    airwallex = parse_case("airwallex", _read("airwallex.html"), labels)
    assert airwallex.video is None
    assert airwallex.founder_handle, "a launch with no video still has a post"


def test_fold_boundary_is_exclusive() -> None:
    launch = parse_case("playerzero", _read("playerzero.html"), parse_index_labels(_read("work.html")))
    assert launch.exceeds_fold is (launch.post_chars > FOLD_CHARS)


class TestVideoRef:
    def test_best_mp4_picks_widest_not_first(self) -> None:
        ref = VideoRef(
            video_id="1",
            duration_ms=1000,
            aspect_ratio=[16, 9],
            view_count=None,
            poster=None,
            mp4_variants={
                "480x270": "low.mp4",
                "1280x720": "high.mp4",
                "640x360": "mid.mp4",
            },
        )
        assert ref.best_mp4() == "high.mp4"

    def test_best_mp4_is_none_when_no_variants(self) -> None:
        ref = VideoRef("1", None, None, None, None, {})
        assert ref.best_mp4() is None

    def test_mp4_at_returns_none_for_missing_label(self) -> None:
        ref = VideoRef("1", None, None, None, None, {"480x270": "low.mp4"})
        assert ref.mp4_at("1920x1080") is None


class TestFlightDecoder:
    def test_extract_returns_none_when_anchor_absent(self) -> None:
        assert extract_json_object('{"a": 1}', "nope") is None

    def test_extract_finds_nested_object(self) -> None:
        text = '{"outer": {"inner": {"favorite_count": 7, "id_str": "x"}}}'
        found = extract_json_object(text, "favorite_count")
        assert found is not None
        assert found["favorite_count"] == 7

    def test_braces_inside_strings_do_not_break_matching(self) -> None:
        text = '{"text": "a { brace } in copy", "favorite_count": 3}'
        found = extract_json_object(text, "favorite_count")
        assert found is not None
        assert found["favorite_count"] == 3
        assert found["text"] == "a { brace } in copy"

    def test_escaped_quote_inside_string_does_not_break_matching(self) -> None:
        text = r'{"text": "he said \"hi\" {", "favorite_count": 9}'
        found = extract_json_object(text, "favorite_count")
        assert found is not None
        assert found["favorite_count"] == 9

    def test_decode_flight_skips_malformed_chunks(self) -> None:
        html = 'self.__next_f.push([1,"good "])self.__next_f.push([1,"tail"])'
        assert decode_flight(html) == "good tail"
