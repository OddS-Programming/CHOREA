from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from mutagen.id3 import ID3

from coverfix.atomic import write_with_backup
from coverfix.core import clean_file, inspect_file
from coverfix.raw import scan_mp3_regions
import helpers


def _audio_sha(path: Path) -> str:
    data = path.read_bytes()
    regions = sorted(scan_mp3_regions(path), key=lambda region: region.offset, reverse=True)
    for region in regions:
        data = data[: region.offset] + data[region.offset + region.size :]
    return hashlib.sha256(data).hexdigest()


def _mp3_with_pictures(tmp_path: Path, asset) -> tuple[Path, list[bytes]]:
    path = asset("mp3", tmp_path / "tone.mp3")
    payloads = helpers.add_mp3_pictures(path)
    return path, payloads


def test_read_reports_all_three_apic(tmp_path: Path, asset) -> None:
    path, payloads = _mp3_with_pictures(tmp_path, asset)
    report = inspect_file(path)

    assert report.container == "mp3"
    assert len(report.pictures) == 3
    assert [picture.type for picture in report.pictures] == [0, 3, 3]
    assert [picture.data for picture in report.pictures] == payloads
    assert report.pictures[1].type_name == "Front Cover"
    assert (report.pictures[1].width, report.pictures[1].height) == (8, 8)
    assert "ID3v2.3" in report.tag_versions


def test_clean_keeps_exactly_one_front_cover(tmp_path: Path, asset) -> None:
    path, payloads = _mp3_with_pictures(tmp_path, asset)
    report = inspect_file(path)

    clean_file(path, keep=report.pictures[2], metadata={"title": "Новое имя", "artist": "Ёж"})

    after = inspect_file(path)
    assert len(after.pictures) == 1
    assert after.pictures[0].type == 3
    assert after.pictures[0].data == payloads[2]
    assert after.fields["title"] == "Новое имя"
    assert after.fields["artist"] == "Ёж"


def test_clean_removes_v1_ape_and_trailing_id3v2(tmp_path: Path, asset) -> None:
    path, _ = _mp3_with_pictures(tmp_path, asset)
    with path.open("ab") as handle:
        handle.write(helpers.id3v2_block(payload=b"\x00" * 24))
        handle.write(helpers.apev2_footer())
        handle.write(helpers.id3v1_block())

    report = inspect_file(path)
    assert any(region.kind == "id3v2" and region.position == "end" for region in report.regions)

    clean_file(path, keep=report.pictures[0], metadata={"title": "Clean"})

    regions = scan_mp3_regions(path)
    assert not [region for region in regions if region.kind in {"id3v1", "apev2"}]
    assert not [region for region in regions if region.kind == "id3v2" and region.position == "end"]


def test_clean_preserves_audio_bytes(tmp_path: Path, asset) -> None:
    path, _ = _mp3_with_pictures(tmp_path, asset)
    before = _audio_sha(path)
    report = inspect_file(path)

    clean_file(path, keep=report.pictures[0], metadata={"title": "Same audio"})

    assert _audio_sha(path) == before
    assert inspect_file(path).audio["duration"] == pytest.approx(report.audio["duration"], abs=0.05)


def test_cyrillic_roundtrip(tmp_path: Path, asset) -> None:
    path, _ = _mp3_with_pictures(tmp_path, asset)
    report = inspect_file(path)
    metadata = {"title": "Тест", "artist": "Ёж", "album": "Альбом", "year": "2024"}

    clean_file(path, keep=report.pictures[0], metadata=metadata, target_id3=3)

    audio = ID3(path)
    assert audio.version[:2] == (2, 3)
    after = inspect_file(path)
    assert after.fields["title"] == "Тест"
    assert after.fields["artist"] == "Ёж"
    assert after.fields["album"] == "Альбом"


def test_clean_without_cover_removes_every_picture(tmp_path: Path, asset) -> None:
    path, _ = _mp3_with_pictures(tmp_path, asset)

    clean_file(path, keep=None, metadata={"title": "No art"})

    assert inspect_file(path).pictures == []


def test_clean_removes_lone_id3v1(tmp_path: Path, asset) -> None:
    path = asset("mp3", tmp_path / "tone.mp3")
    helpers.strip_leading_id3v2(path)
    with path.open("ab") as handle:
        handle.write(helpers.id3v1_block())
    assert {region.kind for region in scan_mp3_regions(path)} == {"id3v1"}

    clean_file(path, keep=None, metadata={"title": "V1 only"})

    assert {region.kind for region in scan_mp3_regions(path)} == {"id3v2"}
    assert inspect_file(path).fields["title"] == "V1 only"


def test_clean_works_on_file_without_tags(tmp_path: Path, asset) -> None:
    path = asset("mp3", tmp_path / "tone.mp3")
    helpers.strip_leading_id3v2(path)
    assert scan_mp3_regions(path) == []

    clean_file(path, keep=None, metadata={"title": "No tags"})

    assert inspect_file(path).fields["title"] == "No tags"


def test_backup_created_and_original_restored_on_error(tmp_path: Path, asset) -> None:
    path, _ = _mp3_with_pictures(tmp_path, asset)
    original = path.read_bytes()

    def broken_writer(target: Path) -> None:
        target.write_bytes(b"corrupted")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        write_with_backup(path, broken_writer)

    assert path.read_bytes() == original
    assert path.with_name(path.name + ".bak").exists()
