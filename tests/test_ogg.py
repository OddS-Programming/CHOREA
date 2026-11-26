from __future__ import annotations

import base64
from pathlib import Path

from mutagen.oggvorbis import OggVorbis

from choreia.core import clean_file, inspect_file
import helpers


def _ogg(tmp_path: Path, asset) -> tuple[Path, bytes]:
    path = asset("ogg", tmp_path / "tone.ogg")
    payload = helpers.add_ogg_picture(path)
    return path, payload


def test_read_decodes_base64_picture(tmp_path: Path, asset) -> None:
    path, payload = _ogg(tmp_path, asset)
    report = inspect_file(path)

    assert report.container == "ogg"
    assert len(report.pictures) == 1
    assert report.pictures[0].data == payload
    assert report.pictures[0].type == 3


def test_clean_leaves_single_picture(tmp_path: Path, asset) -> None:
    path, _ = _ogg(tmp_path, asset)
    report = inspect_file(path)

    clean_file(path, keep=report.pictures[0], metadata={"title": "New", "artist": "Ёж"})

    audio = OggVorbis(path)
    blocks = audio.get("metadata_block_picture", [])
    assert len(blocks) == 1
    decoded = base64.b64decode(blocks[0])
    assert decoded == report.pictures[0].data or b"image/jpeg" in decoded
    after = inspect_file(path)
    assert len(after.pictures) == 1
    assert after.fields["artist"] == "Ёж"
