"""Ogg Vorbis / Opus backend (covers live in the base64 metadata_block_picture comment)."""

from __future__ import annotations

import base64
from pathlib import Path

from mutagen.flac import Picture as FlacPicture
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from .model import FileReport, Picture, make_picture

FIELD_KEYS = {
    "title": "TITLE",
    "artist": "ARTIST",
    "album": "ALBUM",
    "album_artist": "ALBUMARTIST",
    "track": "TRACKNUMBER",
    "disc": "DISCNUMBER",
    "year": "DATE",
    "genre": "GENRE",
}

PICTURE_KEY = "metadata_block_picture"


def _open(path: Path):
    head = Path(path).read_bytes()[:1024]
    return OggOpus(path) if b"OpusHead" in head else OggVorbis(path)


def _decode(encoded: str) -> FlacPicture | None:
    try:
        return FlacPicture(base64.b64decode(encoded))
    except Exception:
        return None


def read(path: Path) -> FileReport:
    path = Path(path)
    audio = _open(path)
    container = "opus" if isinstance(audio, OggOpus) else "ogg"
    report = FileReport(path=path, container=container)
    report.tag_versions.append("Vorbis comments")

    pictures: list[Picture] = []
    tags: dict[str, list[str]] = {}
    for key, values in (audio.tags or {}).items():
        if key.lower() == PICTURE_KEY:
            for encoded in values:
                block = _decode(encoded)
                if block is None:
                    continue
                pictures.append(
                    make_picture(
                        len(pictures),
                        bytes(block.data),
                        type=int(block.type),
                        mime=block.mime,
                        desc=block.desc,
                        width=block.width or None,
                        height=block.height or None,
                        source="vorbis-comment",
                    )
                )
            continue
        tags[key] = [str(value) for value in values]

    report.pictures = pictures
    report.tags = tags

    for name, key in FIELD_KEYS.items():
        for existing, values in tags.items():
            if existing.lower() == key.lower() and values:
                report.fields[name] = values[0]
                break

    try:
        info = audio.info
        report.audio = {
            "duration": round(info.length, 3),
            "bitrate": info.bitrate,
            "sample_rate": info.sample_rate,
            "channels": info.channels,
        }
    except Exception:
        report.audio = {}

    if len(pictures) > 1:
        report.warnings.append(f"в файле {len(pictures)} обложки — плеер может показать не ту")
    return report


def write(path: Path, keep: Picture | None, metadata: dict[str, str], target_id3: int = 3) -> None:
    path = Path(path)
    audio = _open(path)
    if audio.tags is None:
        audio.add_tags()
    tags = audio.tags
    for key in list(tags.keys()):
        del tags[key]

    for name, key in FIELD_KEYS.items():
        value = metadata.get(name, "").strip()
        if value:
            tags[key] = [value]

    if keep is not None:
        block = FlacPicture()
        block.data = keep.data
        block.type = 3
        block.mime = keep.mime if keep.mime != "application/octet-stream" else "image/jpeg"
        block.desc = "Cover"
        block.width = keep.width or 0
        block.height = keep.height or 0
        block.depth = 24
        tags[PICTURE_KEY] = [base64.b64encode(block.write()).decode("ascii")]

    audio.save()
