from __future__ import annotations

from pathlib import Path

import pytest
from mutagen.mp4 import MP4

from choreia.core import clean_file, inspect_file
import helpers


def _mp4(tmp_path: Path, asset) -> tuple[Path, list[bytes]]:
    path = asset("m4a", tmp_path / "tone.m4a")
    payloads = helpers.add_mp4_covers(path)
    return path, payloads


def test_read_reports_multiple_covers(tmp_path: Path, asset) -> None:
    path, payloads = _mp4(tmp_path, asset)
    report = inspect_file(path)

    assert report.container == "m4a"
    assert len(report.pictures) == 2
    assert [picture.data for picture in report.pictures] == payloads
    assert all(picture.source == "mp4-covr" for picture in report.pictures)


def test_clean_writes_one_cover_and_atoms(tmp_path: Path, asset) -> None:
    path, payloads = _mp4(tmp_path, asset)
    report = inspect_file(path)

    clean_file(path, keep=report.pictures[1], metadata={"title": "Новое", "artist": "Ёж", "album": "Альбом"})

    audio = MP4(path)
    assert len(audio.tags["covr"]) == 1
    assert bytes(audio.tags["covr"][0]) == payloads[1]
    assert audio.tags["\xa9nam"] == ["Новое"]
    assert audio.tags["\xa9ART"] == ["Ёж"]
    assert audio.tags["\xa9alb"] == ["Альбом"]


def test_clean_drops_old_atoms(tmp_path: Path, asset) -> None:
    path, _ = _mp4(tmp_path, asset)
    report = inspect_file(path)

    clean_file(path, keep=report.pictures[0], metadata={"title": "Only this"})

    audio = MP4(path)
    assert audio.tags["\xa9nam"] == ["Only this"]
    assert "\xa9ART" not in audio.tags


def test_clean_preserves_audio(tmp_path: Path, asset) -> None:
    path, _ = _mp4(tmp_path, asset)
    before = MP4(path).info.length
    report = inspect_file(path)

    clean_file(path, keep=report.pictures[0], metadata={"title": "x"})

    assert MP4(path).info.length == pytest.approx(before, abs=0.01)
