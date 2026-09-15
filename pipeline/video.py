"""Measure the craft properties of a launch video with ffmpeg.

Cut detection is reported at several thresholds on purpose. A single threshold invites the
reader to trust one magic number; showing that the ordering of videos is stable across
thresholds is what makes the spread a finding rather than a tuning artifact.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path

import imageio_ffmpeg

SCENE_THRESHOLDS = (0.2, 0.3, 0.4)
REPORTING_THRESHOLD = 0.3

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)")
_VIDEO_STREAM_RE = re.compile(r"Stream #\d+:\d+.*?Video:\s*(\w+).*?(\d{2,5})x(\d{2,5}).*?([\d.]+)\s*fps", re.S)
_AUDIO_STREAM_RE = re.compile(r"Stream #\d+:\d+.*?Audio:\s*(\w+)")
_SHOWINFO_TIME_RE = re.compile(r"pts_time:([\d.]+)")


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(args: list[str]) -> str:
    result = subprocess.run(
        [ffmpeg_exe(), *args],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return result.stderr


@dataclass
class VideoMetrics:
    path: str
    duration_s: float
    width: int
    height: int
    fps: float
    codec: str
    has_audio: bool
    cut_counts: dict[str, int] = field(default_factory=dict)
    cut_times: list[float] = field(default_factory=list)

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 0.0

    @property
    def is_landscape(self) -> bool:
        return self.aspect > 1.0

    @property
    def is_cinema_fps(self) -> bool:
        """23.976 or 24 — a film timeline, not a phone-capture default of 30 or 60."""
        return abs(self.fps - 23.976) < 0.05 or abs(self.fps - 24.0) < 0.05

    @property
    def cuts(self) -> int:
        return self.cut_counts.get(str(REPORTING_THRESHOLD), 0)

    @property
    def cuts_per_minute(self) -> float:
        return self.cuts / (self.duration_s / 60) if self.duration_s else 0.0

    @property
    def mean_shot_s(self) -> float:
        return self.duration_s / max(self.cuts, 1)

    def shot_lengths(self) -> list[float]:
        """Gaps between consecutive cuts, bookended by the start and end of the video."""
        if not self.cut_times:
            return [self.duration_s]
        marks = [0.0, *self.cut_times, self.duration_s]
        return [b - a for a, b in zip(marks, marks[1:]) if b > a]

    def cuts_in_window(self, start_frac: float, end_frac: float) -> int:
        lo, hi = self.duration_s * start_frac, self.duration_s * end_frac
        return sum(1 for t in self.cut_times if lo <= t <= hi)

    def mean_shot_in_window(self, start_frac: float, end_frac: float) -> float:
        """Mean shot length for cuts falling inside a fractional window of the runtime.

        With no cut inside the window this returns the window width, which is a placeholder
        rather than a measurement. Callers comparing two windows must check `cuts_in_window`
        first: comparing two placeholders produces a float tie-break, not a finding.
        """
        lo, hi = self.duration_s * start_frac, self.duration_s * end_frac
        marks = [lo, *[t for t in self.cut_times if lo <= t <= hi], hi]
        gaps = [b - a for a, b in zip(marks, marks[1:]) if b > a]
        return sum(gaps) / len(gaps) if gaps else (hi - lo)

    def to_dict(self) -> dict:
        data = asdict(self)
        data.update(
            aspect=round(self.aspect, 4),
            is_landscape=self.is_landscape,
            is_cinema_fps=self.is_cinema_fps,
            cuts=self.cuts,
            cuts_per_minute=round(self.cuts_per_minute, 2),
            mean_shot_s=round(self.mean_shot_s, 2),
        )
        return data


def probe(path: Path) -> tuple[float, int, int, float, str, bool]:
    """Read duration, dimensions, fps, codec and audio presence from ffmpeg's banner."""
    stderr = _run(["-hide_banner", "-i", str(path)])

    duration_match = _DURATION_RE.search(stderr)
    if not duration_match:
        raise ValueError(f"no duration reported for {path}")
    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    video_match = _VIDEO_STREAM_RE.search(stderr)
    if not video_match:
        raise ValueError(f"no video stream found in {path}")
    codec, width, height, fps = video_match.groups()

    return duration, int(width), int(height), float(fps), codec, bool(_AUDIO_STREAM_RE.search(stderr))


def detect_cuts(path: Path, threshold: float) -> list[float]:
    """Timestamps of frames whose scene-change score exceeds `threshold`."""
    stderr = _run(
        [
            "-hide_banner",
            "-i",
            str(path),
            "-filter:v",
            f"select='gt(scene,{threshold})',showinfo",
            "-f",
            "null",
            "-",
        ]
    )
    return [float(t) for t in _SHOWINFO_TIME_RE.findall(stderr)]


def measure(path: Path, thresholds: tuple[float, ...] = SCENE_THRESHOLDS) -> VideoMetrics:
    duration, width, height, fps, codec, has_audio = probe(path)

    cut_counts: dict[str, int] = {}
    cut_times: list[float] = []
    for threshold in thresholds:
        times = detect_cuts(path, threshold)
        cut_counts[str(threshold)] = len(times)
        if threshold == REPORTING_THRESHOLD:
            cut_times = times

    return VideoMetrics(
        path=path.name,
        duration_s=round(duration, 2),
        width=width,
        height=height,
        fps=fps,
        codec=codec,
        has_audio=has_audio,
        cut_counts=cut_counts,
        cut_times=[round(t, 3) for t in cut_times],
    )


def extract_frames(path: Path, times: list[float], out_dir: Path, width: int = 480) -> list[str]:
    """Write one JPEG per timestamp. Returns the filenames written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for index, timestamp in enumerate(times):
        name = f"{path.stem}-{index:02d}.jpg"
        dest = out_dir / name
        if not dest.exists():
            _run(
                [
                    "-hide_banner",
                    "-y",
                    "-ss",
                    f"{timestamp:.3f}",
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-vf",
                    f"scale={width}:-1",
                    str(dest),
                ]
            )
        if dest.exists():
            written.append(name)
    return written


def extract_audio(path: Path, dest: Path) -> Path:
    """Mono 16 kHz MP3, small enough for a speech-to-text API upload."""
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(["-hide_banner", "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(dest)])
    return dest
