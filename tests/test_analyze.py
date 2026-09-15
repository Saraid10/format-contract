"""Hypothesis-evaluation tests.

The point of these is that a verdict cannot drift. If a future change makes a FAILED
hypothesis quietly report HELD, or lets an unmeasurable video count toward a threshold, the
suite fails.
"""

from __future__ import annotations

import pytest

from pipeline.analyze import (
    FAILED,
    HELD,
    INCONCLUSIVE,
    _cv,
    _spearman,
    h1_no_cut_template,
    h2_fixed_container,
    h3_cinema_fps,
    h4_no_spoken_name_in_open,
    h5_front_loaded,
    h6_founders_rarely_on_camera,
    h7_runtime_not_engagement,
    h8_copy_exceeds_fold,
    h9_format_stable_not_converging,
)


def video(slug: str, **kwargs) -> dict:
    base = dict(
        slug=slug,
        company=slug.title(),
        campaign_date="Mar 2026",
        duration_s=150.0,
        width=1280,
        height=720,
        fps=23.976,
        is_landscape=True,
        is_cinema_fps=True,
        has_audio=True,
        favorite_count=1000,
        cut_counts={"0.2": 20, "0.3": 15, "0.4": 10},
        mean_shot_front_quarter=3.0,
        mean_shot_final_quarter=9.0,
        cuts_front_quarter=4,
        cuts_final_quarter=2,
    )
    base.update(kwargs)
    return base


class TestH1:
    def test_wide_spread_holds(self) -> None:
        videos = [
            video("a", cut_counts={"0.2": 54, "0.3": 50, "0.4": 36}),
            video("b", cut_counts={"0.2": 3, "0.3": 0, "0.4": 0}),
        ]
        assert h1_no_cut_template(videos).outcome == HELD

    def test_uniform_cutting_fails(self) -> None:
        videos = [
            video("a", cut_counts={"0.2": 20, "0.3": 18, "0.4": 15}),
            video("b", cut_counts={"0.2": 22, "0.3": 19, "0.4": 16}),
        ]
        assert h1_no_cut_template(videos).outcome == FAILED

    def test_zero_min_does_not_produce_a_ratio(self) -> None:
        """A clamped max/min would manufacture false precision. It must not appear."""
        videos = [
            video("a", cut_counts={"0.2": 54, "0.3": 50, "0.4": 36}),
            video("b", cut_counts={"0.2": 3, "0.3": 0, "0.4": 0}),
        ]
        evidence = h1_no_cut_template(videos).evidence
        assert "max_min_ratio_by_threshold" not in evidence
        assert evidence["spread_by_threshold"]["0.3"]["min"] == 0


class TestH2:
    def test_all_conforming_holds(self) -> None:
        assert h2_fixed_container([video("a"), video("b")]).outcome == HELD

    def test_one_vertical_video_fails_the_whole_claim(self) -> None:
        videos = [video("a"), video("b", is_landscape=False)]
        result = h2_fixed_container(videos)
        assert result.outcome == FAILED
        assert "b" in result.evidence["exceptions"]["vertical"]

    def test_silent_video_fails(self) -> None:
        assert h2_fixed_container([video("a", has_audio=False)]).outcome == FAILED

    @pytest.mark.parametrize("duration", [45.0, 240.0])
    def test_duration_outside_band_fails(self, duration: float) -> None:
        assert h2_fixed_container([video("a", duration_s=duration)]).outcome == FAILED


class TestH3:
    def test_majority_cinema_holds(self) -> None:
        videos = [video(s) for s in "abcd"] + [video("e", is_cinema_fps=False)]
        assert h3_cinema_fps(videos).outcome == HELD

    def test_minority_cinema_fails(self) -> None:
        videos = [video("a"), video("b")] + [video(s, is_cinema_fps=False) for s in "cde"]
        assert h3_cinema_fps(videos).outcome == FAILED


class TestH5:
    def test_video_with_no_cuts_in_a_window_is_excluded_not_counted(self) -> None:
        videos = [
            video("measurable"),
            video("flat", cuts_front_quarter=0, cuts_final_quarter=0,
                  mean_shot_front_quarter=35.0, mean_shot_final_quarter=35.0),
        ]
        result = h5_front_loaded(videos)
        assert "flat" in result.evidence["excluded"]
        assert "flat" not in result.evidence["faster_open"]
        assert "flat" not in result.evidence["slower_open"]
        assert result.evidence["evaluated"] == 1

    def test_equal_windows_never_silently_count_as_front_loaded(self) -> None:
        """The bug this guards: float tie-break filing a no-cut video under faster_open."""
        videos = [
            video("tie", cuts_front_quarter=0, cuts_final_quarter=0,
                  mean_shot_front_quarter=35.087, mean_shot_final_quarter=35.087)
        ]
        result = h5_front_loaded(videos)
        assert result.evidence["faster_open"] == []
        assert result.outcome == FAILED

    def test_five_front_loaded_holds(self) -> None:
        videos = [video(s) for s in "abcde"]
        assert h5_front_loaded(videos).outcome == HELD

    def test_four_front_loaded_fails_the_bound(self) -> None:
        videos = [video(s) for s in "abcd"]
        videos.append(video("e", mean_shot_front_quarter=9.0, mean_shot_final_quarter=3.0))
        assert h5_front_loaded(videos).outcome == FAILED


class TestCredentialGatedHypotheses:
    def test_h4_without_transcripts_is_inconclusive_not_held(self) -> None:
        result = h4_no_spoken_name_in_open([video("a")], {})
        assert result.outcome == INCONCLUSIVE
        assert "no speech-to-text credential" in result.detail

    def test_h6_without_vision_is_inconclusive_not_held(self) -> None:
        result = h6_founders_rarely_on_camera([video("a")], {})
        assert result.outcome == INCONCLUSIVE

    def test_h4_partial_coverage_stays_inconclusive(self) -> None:
        """Half the videos transcribed must not close a 7-video claim."""
        videos = [video("a"), video("b")]
        transcripts = {"a": {"opening_3s": "welcome to the future"}}
        assert h4_no_spoken_name_in_open(videos, transcripts).outcome == INCONCLUSIVE


class TestH7:
    def test_weak_correlation_holds(self) -> None:
        """Four points, because at n=3 Spearman can only be +/-1 or +/-0.5 - there is no
        value that expresses 'weak', and 0.5 sits exactly on the bound the claim rejects."""
        videos = [
            video("a", duration_s=100.0, favorite_count=500),
            video("b", duration_s=150.0, favorite_count=9000),
            video("c", duration_s=200.0, favorite_count=3000),
            video("d", duration_s=250.0, favorite_count=1000),
        ]
        result = h7_runtime_not_engagement(videos)
        assert result.outcome == HELD
        assert abs(result.evidence["spearman_rho"]) < 0.5

    def test_rho_exactly_at_the_bound_fails(self) -> None:
        """The bound is strict: |rho| < 0.5 holds, |rho| == 0.5 does not."""
        videos = [
            video("a", duration_s=100.0, favorite_count=500),
            video("b", duration_s=150.0, favorite_count=9000),
            video("c", duration_s=200.0, favorite_count=3000),
        ]
        result = h7_runtime_not_engagement(videos)
        assert result.evidence["spearman_rho"] == pytest.approx(0.5)
        assert result.outcome == FAILED

    def test_perfect_monotonic_relationship_fails_and_is_called_noise(self) -> None:
        videos = [
            video("a", duration_s=100.0, favorite_count=100),
            video("b", duration_s=150.0, favorite_count=200),
            video("c", duration_s=200.0, favorite_count=300),
        ]
        result = h7_runtime_not_engagement(videos)
        assert result.outcome == FAILED
        assert "noise" in result.detail

    def test_two_points_cannot_correlate(self) -> None:
        videos = [video("a"), video("b")]
        assert h7_runtime_not_engagement(videos).outcome == INCONCLUSIVE


class TestH8:
    def test_majority_over_fold_holds(self) -> None:
        launches = [
            {"slug": s, "exceeds_fold": True, "post_chars": 300} for s in "abcde"
        ]
        assert h8_copy_exceeds_fold(launches).outcome == HELD

    def test_evidence_discloses_the_preregistration_mismatch(self) -> None:
        launches = [{"slug": "a", "exceeds_fold": True, "post_chars": 300}]
        assert "conflating" in h8_copy_exceeds_fold(launches).evidence["note"]


class TestH9:
    def test_collapsing_spread_fails(self) -> None:
        early = [video(f"e{i}", campaign_date="May 2025", duration_s=d)
                 for i, d in enumerate([90.0, 175.0])]
        late = [video(f"l{i}", campaign_date="Mar 2026", duration_s=d)
                for i, d in enumerate([160.0, 165.0])]
        assert h9_format_stable_not_converging(early + late).outcome == FAILED

    def test_stable_spread_holds(self) -> None:
        early = [video(f"e{i}", campaign_date="May 2025", duration_s=d)
                 for i, d in enumerate([90.0, 175.0])]
        late = [video(f"l{i}", campaign_date="Mar 2026", duration_s=d)
                for i, d in enumerate([95.0, 180.0])]
        assert h9_format_stable_not_converging(early + late).outcome == HELD

    def test_tiny_cohort_is_inconclusive(self) -> None:
        videos = [video("a", campaign_date="May 2025"), video("b", campaign_date="Mar 2026")]
        assert h9_format_stable_not_converging(videos).outcome == INCONCLUSIVE


class TestStatistics:
    def test_spearman_perfect_positive(self) -> None:
        assert _spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)

    def test_spearman_perfect_negative(self) -> None:
        assert _spearman([1, 2, 3], [30, 20, 10]) == pytest.approx(-1.0)

    def test_spearman_handles_ties(self) -> None:
        assert _spearman([1, 1, 2, 3], [5, 5, 6, 7]) == pytest.approx(1.0)

    def test_spearman_no_variance_returns_none(self) -> None:
        assert _spearman([1, 1, 1], [2, 2, 2]) is None

    def test_spearman_too_few_points(self) -> None:
        assert _spearman([1, 2], [3, 4]) is None

    def test_cv_is_scale_free(self) -> None:
        assert _cv([10, 20, 30]) == pytest.approx(_cv([100, 200, 300]))

    def test_cv_single_value_is_none(self) -> None:
        assert _cv([5.0]) is None


class TestH6Coverage:
    def test_partial_vision_coverage_cannot_close_the_claim(self) -> None:
        videos = [video("a"), video("b"), video("c")]
        vision = {"a": {"founder_on_camera": False}}
        assert h6_founders_rarely_on_camera(videos, vision).outcome == INCONCLUSIVE

    def test_full_coverage_closes_and_carries_the_identity_caveat(self) -> None:
        videos = [video("a"), video("b")]
        vision = {"a": {"founder_on_camera": True}, "b": {"founder_on_camera": False}}
        result = h6_founders_rarely_on_camera(videos, vision)
        assert result.outcome == HELD
        assert "cannot confirm" in result.evidence["identity_caveat"]

    def test_majority_on_camera_fails(self) -> None:
        videos = [video(s) for s in "abcde"]
        vision = {s: {"founder_on_camera": True} for s in "abcd"}
        vision["e"] = {"founder_on_camera": False}
        assert h6_founders_rarely_on_camera(videos, vision).outcome == FAILED
