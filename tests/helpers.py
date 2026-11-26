"""Shared helpers for building test fixtures with deliberately messy tags."""

from __future__ import annotations

import base64
import io
import shutil
import struct
from pathlib import Path

from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1
from mutagen.mp4 import MP4, MP4Cover

ASSETS = Path(__file__).parent / "assets"


def jpeg(color: tuple[int, int, int] = (200, 30, 30), size: tuple[int, int] = (8, 8)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG", quality=70)
    return buf.getvalue()


def copy_asset(ext: str, dest: Path) -> Path:
    src = ASSETS / f"tone.{ext}"
    if not src.exists():
        raise FileNotFoundError(f"missing fixture {src}; run: python tools/make_assets.py")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def id3v2_block(payload: bytes = b"\x00" * 8, version: int = 3) -> bytes:
    """A syntactically valid empty-ish ID3v2 tag with padding."""
    size = len(payload)
    syncsafe = bytes(
        ((size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F)
    )
    return b"ID3" + bytes((version, 0, 0)) + syncsafe + payload


def id3v1_block() -> bytes:
    return b"TAG" + b"\x00" * 125


def apev2_footer(size: int = 32) -> bytes:
    return (
        b"APETAGEX"
        + struct.pack("<I", 2000)  # version
        + struct.pack("<I", size)  # tag size, footer included
        + struct.pack("<I", 0)  # item count
        + struct.pack("<I", 0)  # flags
        + b"\x00" * 8  # reserved
    )


def strip_leading_id3v2(path: Path) -> Path:
    """Rewrite the file without its leading ID3v2 tag, keeping the audio frames."""
    data = path.read_bytes()
    if data[:3] == b"ID3":
        size = (
            ((data[6] & 0x7F) << 21)
            | ((data[7] & 0x7F) << 14)
            | ((data[8] & 0x7F) << 7)
            | (data[9] & 0x7F)
        )
        data = data[10 + size :]
    path.write_bytes(data)
    return path


def add_mp3_pictures(path: Path, types: tuple[int, ...] = (0, 3, 3)) -> list[bytes]:
    tags = ID3()
    tags.add(TIT2(encoding=1, text=["Original title"]))
    tags.add(TPE1(encoding=1, text=["Original artist"]))
    tags.add(TALB(encoding=1, text=["Original album"]))
    payloads = []
    for i, picture_type in enumerate(types):
        data = jpeg(((i + 1) * 60, 10, 200 - i * 40))
        payloads.append(data)
        tags.add(
            APIC(
                encoding=1,
                mime="image/jpeg",
                type=picture_type,
                desc=f"picture {i}",
                data=data,
            )
        )
    tags.save(path, v1=1, v2_version=3)
    return payloads


def add_flac_pictures(path: Path) -> list[bytes]:
    audio = FLAC(path)
    audio.clear_pictures()
    payloads = []
    for i, picture_type in enumerate((3, 0)):
        data = jpeg((10, (i + 1) * 90, 30))
        payloads.append(data)
        picture = Picture()
        picture.data = data
        picture.type = picture_type
        picture.mime = "image/jpeg"
        picture.width = 8
        picture.height = 8
        picture.depth = 24
        audio.add_picture(picture)
    # A second cover hidden where mp3tag does not look: a Vorbis comment.
    hidden = Picture()
    hidden.data = jpeg((0, 0, 240))
    hidden.type = 3
    hidden.mime = "image/jpeg"
    hidden.width = 8
    hidden.height = 8
    hidden.depth = 24
    audio.tags["metadata_block_picture"] = [base64.b64encode(hidden.write()).decode("ascii")]
    audio.save()
    return payloads


def add_mp4_covers(path: Path, count: int = 2) -> list[bytes]:
    audio = MP4(path)
    if audio.tags is None:
        audio.add_tags()
    payloads = []
    covers = []
    for i in range(count):
        data = jpeg(((i + 1) * 100, 40, 40))
        payloads.append(data)
        covers.append(MP4Cover(data, imageformat=MP4Cover.FORMAT_JPEG))
    audio.tags["covr"] = covers
    audio.tags["\xa9nam"] = ["Original title"]
    audio.tags["\xa9ART"] = ["Original artist"]
    audio.save()
    return payloads


def add_ogg_picture(path: Path) -> bytes:
    from mutagen.oggvorbis import OggVorbis

    audio = OggVorbis(path)
    picture = Picture()
    picture.data = jpeg((30, 120, 30))
    picture.type = 3
    picture.mime = "image/jpeg"
    picture.width = 8
    picture.height = 8
    picture.depth = 24
    audio["metadata_block_picture"] = [base64.b64encode(picture.write()).decode("ascii")]
    audio.save()
    return picture.data
