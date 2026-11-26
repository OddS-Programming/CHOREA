"""Walk music folders and keep the SQLite index in sync."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

from ..core import inspect_file
from .db import Library
from .thumbs import ThumbCache

AUDIO_SUFFIXES = {".mp3", ".flac", ".m4a", ".m4b", ".mp4", ".ogg", ".oga", ".opus", ".aac", ".wav"}

Progress = Callable[[int, int], None]


@dataclass
class ScanResult:
    total: int = 0
    added: int = 0
    updated: int = 0
    removed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "added": self.added,
            "updated": self.updated,
            "removed": self.removed,
            "errors": self.errors,
        }


def iter_audio(folder: Path) -> Iterator[Path]:
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES:
            yield path


def _number(value: str) -> int | None:
    head = (value or "").split("/")[0].strip()
    try:
        return int(head)
    except ValueError:
        return None


def refresh_track(library: Library, thumbs: ThumbCache, path: Path | str) -> dict | None:
    """Re-read one file after an edit and update its row in the index."""
    path = Path(path)
    report = inspect_file(path)
    existing = library.track_by_path(str(path))
    cover = report.front_cover
    cover_hash = thumbs.store(cover.data) if cover is not None else ""
    stat = path.stat()
    fields = report.fields
    library.upsert_track(
        path=str(path),
        folder_id=existing["folder_id"] if existing else None,
        title=fields.get("title") or path.stem,
        artist=fields.get("artist", ""),
        album=fields.get("album", ""),
        album_artist=fields.get("album_artist", ""),
        track_no=_number(fields.get("track", "")),
        disc_no=_number(fields.get("disc", "")),
        year=fields.get("year", ""),
        genre=fields.get("genre", ""),
        duration=report.audio.get("duration", 0) or 0,
        bitrate=report.audio.get("bitrate", 0) or 0,
        sample_rate=report.audio.get("sample_rate", 0) or 0,
        channels=report.audio.get("channels", 0) or 0,
        size=stat.st_size,
        mtime=stat.st_mtime,
        cover_hash=cover_hash,
        added_at=time.time(),
    )
    return library.track_by_path(str(path))


class Scanner:
    def __init__(
        self,
        library: Library,
        thumbs: ThumbCache,
        progress: Progress | None = None,
    ) -> None:
        self.library = library
        self.thumbs = thumbs
        self.progress = progress

    def scan_folder(self, folder: Path | str) -> ScanResult:
        folder = Path(folder)
        if not folder.is_dir():
            raise NotADirectoryError(str(folder))

        folder_id = self.library.add_folder(folder)
        files = list(iter_audio(folder))
        result = ScanResult(total=len(files))
        seen: set[str] = set()

        for index, path in enumerate(files, start=1):
            seen.add(str(path))
            try:
                self._scan_file(path, folder_id, result)
            except Exception as exc:  # a broken file must not stop the scan
                result.errors.append(f"{path.name}: {exc}")
            if self.progress is not None:
                self.progress(index, len(files))

        for track in self.library.tracks_under(str(folder)):
            if track["path"] not in seen:
                self.library.delete_tracks([track["path"]])
                result.removed += 1

        return result

    def _scan_file(self, path: Path, folder_id: int, result: ScanResult) -> None:
        stat = path.stat()
        existing = self.library.track_by_path(str(path))
        if (
            existing is not None
            and abs(float(existing["mtime"]) - stat.st_mtime) < 1e-6
            and int(existing["size"]) == stat.st_size
        ):
            return

        report = inspect_file(path)
        cover = report.front_cover
        cover_hash = None
        if cover is not None:
            cover_hash, _ = self.thumbs.ensure(cover.data, 320)

        fields = report.fields
        self.library.upsert_track(
            path=str(path),
            folder_id=folder_id,
            title=fields.get("title") or path.stem,
            artist=fields.get("artist", ""),
            album=fields.get("album", ""),
            album_artist=fields.get("album_artist", ""),
            track_no=_number(fields.get("track", "")),
            disc_no=_number(fields.get("disc", "")),
            year=fields.get("year", ""),
            genre=fields.get("genre", ""),
            duration=report.audio.get("duration", 0) or 0,
            bitrate=report.audio.get("bitrate", 0) or 0,
            sample_rate=report.audio.get("sample_rate", 0) or 0,
            channels=report.audio.get("channels", 0) or 0,
            size=stat.st_size,
            mtime=stat.st_mtime,
            cover_hash=cover_hash or "",
            added_at=time.time(),
        )

        if existing is None:
            result.added += 1
        else:
            result.updated += 1
