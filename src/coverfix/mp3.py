"""MP3 / ID3v2 backend."""

from __future__ import annotations

from pathlib import Path

from mutagen.apev2 import APENoHeaderError, APEv2
from mutagen.id3 import (
    APIC,
    ID3,
    ID3NoHeaderError,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TPE1,
    TPE2,
    TPOS,
    TRCK,
)
from mutagen.mp3 import MP3

from .model import FileReport, Picture, make_picture
from .raw import scan_mp3_regions

FIELD_FRAMES = {
    "title": "TIT2",
    "artist": "TPE1",
    "album": "TALB",
    "album_artist": "TPE2",
    "track": "TRCK",
    "disc": "TPOS",
    "year": "TDRC",
    "genre": "TCON",
}


def _read_fields(tag: ID3) -> dict[str, str]:
    fields: dict[str, str] = {}
    for name, frame_id in FIELD_FRAMES.items():
        frame = tag.get(frame_id)
        if frame is None:
            continue
        text = getattr(frame, "text", None)
        if text:
            fields[name] = " / ".join(str(value) for value in text)
    return fields


def _read_tags(tag: ID3) -> dict[str, list[str]]:
    tags: dict[str, list[str]] = {}
    for key, frame in tag.items():
        if key.startswith("APIC"):
            continue
        text = getattr(frame, "text", None)
        tags[key] = [str(value) for value in text] if text else [str(frame)]
    return tags


def read(path: Path) -> FileReport:
    path = Path(path)
    report = FileReport(path=path, container="mp3")
    report.regions = scan_mp3_regions(path)

    tag: ID3 | None = None
    try:
        tag = ID3(path)
    except ID3NoHeaderError:
        report.warnings.append("ID3v2-тег не найден")
    except Exception as exc:  # a corrupt tag must not stop the inspection
        report.warnings.append(f"ID3v2-тег не читается: {exc}")

    if tag is not None:
        report.tag_versions.append(f"ID3v2.{tag.version[1]}")
        pictures = [
            make_picture(
                index,
                bytes(frame.data),
                type=int(frame.type),
                mime=frame.mime,
                desc=frame.desc,
                source="id3",
            )
            for index, frame in enumerate(tag.getall("APIC"))
        ]
        report.pictures = pictures
        report.tags = _read_tags(tag)
        report.fields = _read_fields(tag)

    if any(region.kind == "id3v1" for region in report.regions):
        report.tag_versions.append("ID3v1")
    if any(region.kind == "apev2" for region in report.regions):
        report.tag_versions.append("APEv2")
    if any(region.kind == "id3v2" and region.position == "end" for region in report.regions):
        report.tag_versions.append("ID3v2 (в конце файла)")
        report.warnings.append(
            "в файле второй ID3v2-тег в конце — большинство редакторов его не показывает"
        )

    try:
        info = MP3(path).info
        report.audio = {
            "duration": round(info.length, 3),
            "bitrate": info.bitrate,
            "sample_rate": info.sample_rate,
            "channels": info.channels,
        }
    except Exception:
        report.audio = {}

    if len(report.pictures) > 1:
        report.warnings.append(f"в файле {len(report.pictures)} обложки — плеер может показать не ту")
    return report


def _strip(path: Path) -> None:
    # Remove tags in passes: an unusual order (for example APEv2 before a
    # trailing ID3v2) only becomes reachable once the block after it is gone.
    for _ in range(4):
        before = path.stat().st_size

        try:
            ID3().delete(path)
        except ID3NoHeaderError:
            pass

        try:
            APEv2(path).delete()
        except APENoHeaderError:
            pass

        stale = [
            region
            for region in scan_mp3_regions(path)
            if region.kind in {"apev2", "id3v1"}
            or (region.kind == "id3v2" and region.position == "end")
        ]
        if stale:
            cut = min(region.offset for region in stale)
            with path.open("r+b") as handle:
                handle.truncate(cut)

        if path.stat().st_size == before:
            break


def write(path: Path, keep: Picture | None, metadata: dict[str, str], target_id3: int = 3) -> None:
    path = Path(path)
    _strip(path)

    tag = ID3()
    text = {name: metadata.get(name, "").strip() for name in FIELD_FRAMES}
    if text["title"]:
        tag.add(TIT2(encoding=1, text=[text["title"]]))
    if text["artist"]:
        tag.add(TPE1(encoding=1, text=[text["artist"]]))
    if text["album"]:
        tag.add(TALB(encoding=1, text=[text["album"]]))
    if text["album_artist"]:
        tag.add(TPE2(encoding=1, text=[text["album_artist"]]))
    if text["track"]:
        tag.add(TRCK(encoding=1, text=[text["track"]]))
    if text["disc"]:
        tag.add(TPOS(encoding=1, text=[text["disc"]]))
    if text["year"]:
        tag.add(TDRC(encoding=1, text=[text["year"]]))
    if text["genre"]:
        tag.add(TCON(encoding=1, text=[text["genre"]]))

    if keep is not None:
        tag.add(
            APIC(
                encoding=1,
                mime=keep.mime if keep.mime != "application/octet-stream" else "image/jpeg",
                type=3,
                desc="Cover",
                data=keep.data,
            )
        )

    if target_id3 == 4:
        tag.update_to_v24()
        tag.save(path, v1=0, v2_version=4)
    else:
        tag.update_to_v23()
        tag.save(path, v1=0, v2_version=3)
