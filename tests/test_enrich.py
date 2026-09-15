"""Tests for the opening-window slice that H4 depends on.

H4 asks what is spoken in the first three seconds. Getting that window wrong — by falling back
to a character slice of the full transcript, say — would produce a confident answer to the
wrong question.
"""

from __future__ import annotations

from pipeline.enrich import _opening_text


class TestOpeningWindow:
    def test_word_timestamps_are_preferred(self) -> None:
        result = {
            "words": [
                {"word": "this", "start": 0.1},
                {"word": "is", "start": 0.6},
                {"word": "Gamma", "start": 5.0},
            ],
            "segments": [{"text": "ignore me", "start": 0.0}],
            "text": "this is Gamma",
        }
        assert _opening_text(result) == "this is"

    def test_segments_used_when_no_words(self) -> None:
        result = {
            "segments": [
                {"text": "opening line", "start": 0.0},
                {"text": "later line", "start": 9.0},
            ]
        }
        assert _opening_text(result) == "opening line"

    def test_no_timestamps_returns_empty_rather_than_guessing(self) -> None:
        """A character slice of the full transcript is not a three-second window."""
        assert _opening_text({"text": "some long transcript with no timing at all"}) == ""

    def test_boundary_word_is_excluded(self) -> None:
        result = {"words": [{"word": "in", "start": 2.99}, {"word": "out", "start": 3.0}]}
        assert _opening_text(result) == "in"

    def test_window_is_configurable(self) -> None:
        result = {"words": [{"word": "a", "start": 1.0}, {"word": "b", "start": 4.0}]}
        assert _opening_text(result, window=5.0) == "a b"

    def test_word_missing_start_is_not_counted(self) -> None:
        result = {"words": [{"word": "kept", "start": 0.5}, {"word": "unstamped"}]}
        assert _opening_text(result) == "kept"

    def test_empty_input_is_empty(self) -> None:
        assert _opening_text({}) == ""
