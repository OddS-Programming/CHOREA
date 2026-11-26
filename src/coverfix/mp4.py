"""MP4 / M4A backend."""

from __future__ import annotations

from pathlib import Path

from mutagen.mp4 import MP4, MP4Cover

from .model import FileReport, Picture, make_picture

FIELD_ATOMS = {
    "title": "\xa9nam",
    "artist": "\xa9ART",
    "album": "\xa9alb",
    "album_artist": "aART",
    "year": "\xa9day",
    "genre": "\xa9gen",
}

COVER_FORMATS = {
    "image/jpeg": MP4Cover.FORMAT_JPEG,
    "image/png": MP4Cover.FORMAT_PNG,
}


def _first(tags: dict, key: str) -> str:
    values = tags.get(key)
    if not values:
        return ""
    value = values[0]
    return str(value)


def read(path: Path) -> FileReport:
    path = Path(path)
    audio = MP4(path)
    report = FileReport(path=path, container="m4a")
    report.tag_versions.append("MP4 ilst")

    tags = audio.tags or {}
    report.pictures = [
        make_picture(
            index,
            bytes(cover),
            type=3,
            mime="image/png" if int(cover.imageformat) == MP4Cover.FORMAT_PNG else "image/jpeg",
            desc="",
            source="mp4-covr",
        )
        for index, cover in enumerate(tags.get("covr", []))
    ]

    report.tags = {key: [str(value) for value in values] for key, values in tags.items() if key != "covr"}
    for name, atom in FIELD_ATOMS.items():
        value = _first(tags, atom)
        if value:
            report.fields[name] = value

    track = tags.get("trkn")
    if track:
        number, total = track[0]
        report.fields["track"] = f"{number}/{total}" if total else str(number)
    disc = tags.get("disk")
    if disc:
        number, total = disc[0]
        report.fields["disc"] = f"{number}/{total}" if total else str(number)

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

    if len(report.pictures) > 1:
        report.warnings.append(
            f"в файле {len(report.pictures)} обложки в атоме covr — плеер может показать не ту"
        )
    return report


def _number_pair(value: str) -> tuple[int, int]:
    text = value.strip()
    if not text:
        return (0, 0)
    left, _, right = text.partition("/")
    try:
        number = int(left)
    except ValueError:
        return (0, 0)
    try:
        total = int(right) if right.strip() else 0
    except ValueError:
        total = 0
    return (number, total)


def write(path: Path, keep: Picture | None, metadata: dict[str, str], target_id3: int = 3) -> None:
    path = Path(path)
    audio = MP4(path)
    if audio.tags is None:
        audio.add_tags()
    else:
        for key in list(audio.tags.keys()):
            del audio.tags[key]
    tags = audio.tags

    for name, atom in FIELD_ATOMS.items():
        value = metadata.get(name, "").strip()
        if value:
            tags[atom] = [value]

    track = _number_pair(metadata.get("track", ""))
    if track[0]:
        tags["trkn"] = [track]
    disc = _number_pair(metadata.get("disc", ""))
    if disc[0]:
        tags["disk"] = [disc]

    if keep is not None:
        image_format = COVER_FORMATS.get(keep.mime, MP4Cover.FORMAT_JPEG)
        tags["covr"] = [MP4Cover(keep.data, imageformat=image_format)]

    audio.save()
