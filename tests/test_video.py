"""Metric-math tests.

These exercise VideoMetrics as pure arithmetic over synthetic inputs. They do not need ffmpeg
or any downloaded media, so the shot-length and windowing logic is verified even on a machine
that has never run the pipeline.
"""

from __future__ import annotations

import pytest

from pipeline.video import VideoMetrics


def make(duration: float = 100.0, cut_times: list[float] | None = None, **kwargs) -> VideoMetrics:
    cut_times = [] if cut_times is None else cut_times
    defaults = dict(
        path="x.mp4",
        duration_s=duration,
        width=1280,
        height=720,
        fps=23.976,
        codec="h264",
        has_audio=True,
        cut_counts={"0.3": len(cut_times)},
        cut_times=cut_times,
    )
    defaults.update(kwargs)
    return VideoMetrics(**defaults)


class TestOrientation:
    def test_landscape_detected(self) -> None:
        assert make().is_landscape

    def test_vertical_detected(self) -> None:
        assert not make(width=720, height=1280).is_landscape

    def test_square_is_not_landscape(self) -> None:
        assert not make(width=720, height=720).is_landscape

    def test_zero_height_does_not_raise(self) -> None:
        assert make(height=0).aspect == 0.0


class TestCinemaFps:
    @pytest.mark.parametrize("fps", [23.976, 23.98, 24.0])
    def test_film_rates_accepted(self, fps: float) -> None:
        assert make(fps=fps).is_cinema_fps

    @pytest.mark.parametrize("fps", [25.0, 29.97, 30.0, 60.0])
    def test_broadcast_and_phone_rates_rejected(self, fps: float) -> None:
        assert not make(fps=fps).is_cinema_fps


class TestShotLengths:
    def test_no_cuts_is_one_shot_of_full_duration(self) -> None:
        assert make(duration=100.0, cut_times=[]).shot_lengths() == [100.0]

    def test_cuts_bookended_by_start_and_end(self) -> None:
        shots = make(duration=100.0, cut_times=[25.0, 50.0]).shot_lengths()
        assert shots == [25.0, 25.0, 50.0]

    def test_shot_lengths_sum_to_duration(self) -> None:
        metrics = make(duration=90.0, cut_times=[10.0, 20.0, 75.0])
        assert sum(metrics.shot_lengths()) == pytest.approx(90.0)

    def test_duplicate_cut_times_do_not_emit_zero_length_shots(self) -> None:
        shots = make(duration=60.0, cut_times=[30.0, 30.0]).shot_lengths()
        assert all(s > 0 for s in shots)

    def test_mean_shot_never_divides_by_zero(self) -> None:
        assert make(duration=50.0, cut_times=[]).mean_shot_s == 50.0

    def test_mean_shot_counts_cuts_plus_one_shots(self) -> None:
        assert make(duration=100.0, cut_times=[50.0]).mean_shot_s == 50.0


class TestRates:
    def test_cuts_per_minute(self) -> None:
        metrics = make(duration=120.0, cut_times=[float(t) for t in range(1, 21)])
        assert metrics.cuts_per_minute == pytest.approx(10.0)

    def test_zero_duration_yields_zero_rate(self) -> None:
        assert make(duration=0.0).cuts_per_minute == 0.0

    def test_cuts_reads_the_reporting_threshold(self) -> None:
        metrics = make(cut_counts={"0.2": 99, "0.3": 42, "0.4": 7})
        assert metrics.cuts == 42

    def test_cuts_defaults_to_zero_when_threshold_absent(self) -> None:
        assert make(cut_counts={"0.9": 5}).cuts == 0


class TestWindowedShots:
    def test_front_window_reflects_dense_cutting(self) -> None:
        """Cuts packed into the opening quarter; the front window must read shorter."""
        metrics = make(duration=100.0, cut_times=[2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0])
        front = metrics.mean_shot_in_window(0.0, 0.25)
        back = metrics.mean_shot_in_window(0.75, 1.0)
        assert front < back

    def test_empty_window_falls_back_to_window_width(self) -> None:
        metrics = make(duration=100.0, cut_times=[50.0])
        assert metrics.mean_shot_in_window(0.0, 0.25) == pytest.approx(25.0)

    def test_cut_on_the_boundary_makes_no_phantom_zero_length_shot(self) -> None:
        """A cut exactly on the edge bounds one shot spanning the window, not two."""
        metrics = make(duration=100.0, cut_times=[25.0])
        shots_in_window = metrics.mean_shot_in_window(0.0, 0.25)
        assert shots_in_window == pytest.approx(25.0)

    def test_interior_cut_splits_the_window(self) -> None:
        metrics = make(duration=100.0, cut_times=[12.5])
        assert metrics.mean_shot_in_window(0.0, 0.25) == pytest.approx(12.5)


def test_to_dict_carries_derived_fields() -> None:
    data = make(duration=100.0, cut_times=[50.0]).to_dict()
    assert data["is_landscape"] is True
    assert data["is_cinema_fps"] is True
    assert data["cuts"] == 1
    assert data["mean_shot_s"] == 50.0
