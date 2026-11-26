"""FLAC backend."""

from __future__ import annotations

import base64
from pathlib import Path

from mutagen.flac import FLAC, Picture as FlacPicture

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


def _picture_from_block(index: int, block: FlacPicture, source: str) -> Picture:
    return make_picture(
        index,
        bytes(block.data),
        type=int(block.type),
        mime=block.mime,
        desc=block.desc,
        width=block.width or None,
        height=block.height or None,
        source=source,
    )


def _read_comment_pictures(audio: FLAC) -> list[FlacPicture]:
    found: list[FlacPicture] = []
    for key, values in (audio.tags or {}).items():
        if key.lower() != "metadata_block_picture":
            continue
        for encoded in values:
            try:
                found.append(FlacPicture(base64.b64decode(encoded)))
            except Exception:
                continue
    return found


def read(path: Path) -> FileReport:
    path = Path(path)
    audio = FLAC(path)
    report = FileReport(path=path, container="flac")
    report.tag_versions.append("Vorbis comments")

    pictures = [_picture_from_block(index, block, "flac-picture") for index, block in enumerate(audio.pictures)]
    for block in _read_comment_pictures(audio):
        pictures.append(_picture_from_block(len(pictures), block, "vorbis-comment"))
    report.pictures = pictures

    tags: dict[str, list[str]] = {}
    for key, values in (audio.tags or {}).items():
        if key.lower() == "metadata_block_picture":
            continue
        tags[key] = [str(value) for value in values]
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

    if any(picture.source == "vorbis-comment" for picture in pictures):
        report.warnings.append(
            "обложка спрятана в Vorbis-комментарии (metadata_block_picture) — mp3tag её не показывает"
        )
    if len(pictures) > 1:
        report.warnings.append(f"в файле {len(pictures)} обложки — плеер может показать не ту")
    return report


def _to_flac_picture(picture: Picture) -> FlacPicture:
    block = FlacPicture()
    block.data = picture.data
    block.type = 3
    block.mime = picture.mime if picture.mime != "application/octet-stream" else "image/jpeg"
    block.desc = "Cover"
    block.width = picture.width or 0
    block.height = picture.height or 0
    block.depth = 24
    return block


def write(path: Path, keep: Picture | None, metadata: dict[str, str], target_id3: int = 3) -> None:
    path = Path(path)
    audio = FLAC(path)
    audio.clear_pictures()
    if audio.tags is not None:
        for key in [existing for existing in audio.tags.keys() if existing.lower() == "metadata_block_picture"]:
            del audio.tags[key]

    if audio.tags is None:
        audio.add_tags()
    audio.tags.clear()

    for name, key in FIELD_KEYS.items():
        value = metadata.get(name, "").strip()
        if value:
            audio.tags[key] = [value]

    if keep is not None:
        audio.add_picture(_to_flac_picture(keep))

    audio.save(deleteid3=True)
