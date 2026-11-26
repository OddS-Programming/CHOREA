from __future__ import annotations

from pathlib import Path

from mutagen.flac import FLAC

from coverfix.core import clean_file, inspect_file
import helpers


def _flac(tmp_path: Path, asset) -> tuple[Path, list[bytes]]:
    path = asset("flac", tmp_path / "tone.flac")
    payloads = helpers.add_flac_pictures(path)
    return path, payloads


def test_read_finds_picture_block_and_vorbis_comment(tmp_path: Path, asset) -> None:
    path, payloads = _flac(tmp_path, asset)
    report = inspect_file(path)

    assert report.container == "flac"
    assert len(report.pictures) == 3
    assert [picture.source for picture in report.pictures].count("flac-picture") == 2
    assert "vorbis-comment" in [picture.source for picture in report.pictures]
    assert payloads[0] in [picture.data for picture in report.pictures]


def test_clean_removes_both_sources(tmp_path: Path, asset) -> None:
    path, _ = _flac(tmp_path, asset)
    report = inspect_file(path)

    clean_file(path, keep=report.pictures[0], metadata={"title": "New"})

    audio = FLAC(path)
    assert len(audio.pictures) == 1
    keys = {key.lower() for key in (audio.tags or {}).keys()}
    assert "metadata_block_picture" not in keys


def test_clean_writes_one_front_cover(tmp_path: Path, asset) -> None:
    path, payloads = _flac(tmp_path, asset)
    report = inspect_file(path)

    clean_file(path, keep=report.pictures[0], metadata={"title": "New", "artist": "Ёж"})

    after = inspect_file(path)
    assert len(after.pictures) == 1
    assert after.pictures[0].type == 3
    assert after.pictures[0].data == payloads[0]
    assert after.fields["artist"] == "Ёж"


def test_clean_without_cover(tmp_path: Path, asset) -> None:
    path, _ = _flac(tmp_path, asset)
    clean_file(path, keep=None, metadata={"title": "No art"})
    assert inspect_file(path).pictures == []
