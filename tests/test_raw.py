from __future__ import annotations

from pathlib import Path

from coverfix.raw import scan_mp3_regions
from helpers import apev2_footer, copy_asset, id3v1_block, id3v2_block
import helpers


def _mp3(tmp_path: Path) -> Path:
    return copy_asset("mp3", tmp_path / "tone.mp3")


def test_reports_leading_id3v2(tmp_path: Path) -> None:
    path = _mp3(tmp_path)
    helpers.add_mp3_pictures(path)
    regions = scan_mp3_regions(path)
    leading = [r for r in regions if r.kind == "id3v2" and r.position == "start"]
    assert len(leading) == 1
    assert leading[0].offset == 0
    assert leading[0].size > 10


def test_reports_trailing_id3v2(tmp_path: Path) -> None:
    path = _mp3(tmp_path)
    helpers.add_mp3_pictures(path)
    blob = id3v2_block(payload=b"\x00" * 16)
    before = path.stat().st_size
    with path.open("ab") as handle:
        handle.write(blob)

    regions = scan_mp3_regions(path)
    trailing = [r for r in regions if r.kind == "id3v2" and r.position == "end"]
    assert len(trailing) == 1
    assert trailing[0].offset == before
    assert trailing[0].size == len(blob)


def test_reports_id3v1_and_ape(tmp_path: Path) -> None:
    path = _mp3(tmp_path)
    helpers.add_mp3_pictures(path)
    with path.open("ab") as handle:
        handle.write(apev2_footer())
        handle.write(id3v1_block())

    found = {(r.kind, r.position) for r in scan_mp3_regions(path)}
    assert ("apev2", "end") in found
    assert ("id3v1", "end") in found


def test_trailing_id3v2_followed_by_v1_and_ape_is_located(tmp_path: Path) -> None:
    path = _mp3(tmp_path)
    helpers.add_mp3_pictures(path)
    blob = id3v2_block(payload=b"\x00" * 24)
    offset = path.stat().st_size
    with path.open("ab") as handle:
        handle.write(blob)
        handle.write(apev2_footer())
        handle.write(id3v1_block())

    trailing = [r for r in scan_mp3_regions(path) if r.kind == "id3v2" and r.position == "end"]
    assert len(trailing) == 1
    assert trailing[0].offset == offset
    assert trailing[0].size == len(blob)


def test_clean_file_has_no_trailing_regions(tmp_path: Path) -> None:
    path = _mp3(tmp_path)
    helpers.add_mp3_pictures(path)
    regions = scan_mp3_regions(path)
    assert regions
