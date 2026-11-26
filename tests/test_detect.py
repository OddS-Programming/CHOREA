from __future__ import annotations

from pathlib import Path

from coverfix.detect import detect_container


def test_detect_mp3_by_magic_not_extension(tmp_path: Path, asset) -> None:
    path = asset("mp3", tmp_path / "tone.flac")
    container = detect_container(path)
    assert container.code == "mp3"
    assert "flac" in container.note


def test_detect_flac(tmp_path: Path, asset) -> None:
    container = detect_container(asset("flac", tmp_path / "tone.flac"))
    assert container.code == "flac"
    assert container.note == ""


def test_detect_m4a(tmp_path: Path, asset) -> None:
    container = detect_container(asset("m4a", tmp_path / "tone.m4a"))
    assert container.code == "m4a"
    assert container.note == ""


def test_detect_ogg(tmp_path: Path, asset) -> None:
    container = detect_container(asset("ogg", tmp_path / "tone.ogg"))
    assert container.code in {"ogg", "opus"}


def test_detect_matroska_explains_video_stream(tmp_path: Path) -> None:
    path = tmp_path / "fake.mp3"
    path.write_bytes(b"\x1aE\xdf\xa3" + b"\x00" * 64)
    container = detect_container(path)
    assert container.code == "matroska"
    assert "видеопоток" in container.note


def test_detect_unknown(tmp_path: Path) -> None:
    path = tmp_path / "noise.bin"
    path.write_bytes(b"not audio at all" * 8)
    container = detect_container(path)
    assert container.code == "unknown"
