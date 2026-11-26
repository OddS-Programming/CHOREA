from __future__ import annotations

import os
from pathlib import Path

from choreia.library.db import Library
from choreia.library.scanner import Scanner
from choreia.library.thumbs import ThumbCache
import helpers


def _setup(tmp_path: Path) -> tuple[Library, Scanner]:
    library = Library(tmp_path / "library.db")
    return library, Scanner(library, ThumbCache(tmp_path / "thumbs"))


def test_scan_adds_tracks_from_folder(tmp_path: Path, asset) -> None:
    folder = tmp_path / "Album"
    folder.mkdir()
    helpers.add_mp3_pictures(helpers.copy_asset("mp3", folder / "01.mp3"))
    helpers.copy_asset("flac", folder / "02.flac")

    library, scanner = _setup(tmp_path)
    result = scanner.scan_folder(folder)

    assert result.total == 2
    assert result.added == 2
    tracks = library.list_tracks(sort="title")
    assert len(tracks) == 2
    assert any(track["title"] == "Original title" for track in tracks)
    library.close()


def test_rescan_is_incremental(tmp_path: Path, asset) -> None:
    folder = tmp_path / "Album"
    folder.mkdir()
    first = helpers.copy_asset("mp3", folder / "01.mp3")
    helpers.add_mp3_pictures(first)
    helpers.copy_asset("flac", folder / "02.flac")

    library, scanner = _setup(tmp_path)
    scanner.scan_folder(folder)

    again = scanner.scan_folder(folder)
    assert (again.added, again.updated) == (0, 0)

    stamp = os.stat(first).st_mtime + 10
    os.utime(first, (stamp, stamp))
    changed = scanner.scan_folder(folder)
    assert (changed.added, changed.updated) == (0, 1)
    library.close()


def test_scan_removes_deleted_files(tmp_path: Path, asset) -> None:
    folder = tmp_path / "Album"
    folder.mkdir()
    helpers.copy_asset("mp3", folder / "01.mp3")
    second = helpers.copy_asset("flac", folder / "02.flac")

    library, scanner = _setup(tmp_path)
    scanner.scan_folder(folder)
    second.unlink()

    result = scanner.scan_folder(folder)

    assert result.removed == 1
    assert library.count_tracks() == 1
    library.close()


def test_cyrillic_folder_path_is_preserved(tmp_path: Path, asset) -> None:
    folder = tmp_path / "Музыка" / "Альбом"
    folder.mkdir(parents=True)
    helpers.copy_asset("mp3", folder / "трек.mp3")

    library, scanner = _setup(tmp_path)
    scanner.scan_folder(folder)

    tracks = library.list_tracks()
    assert len(tracks) == 1
    assert "Музыка" in tracks[0]["path"]
    assert tracks[0]["path"].endswith("трек.mp3")
    library.close()


def test_cover_thumbnail_is_cached(tmp_path: Path, asset) -> None:
    folder = tmp_path / "Album"
    folder.mkdir()
    helpers.add_mp3_pictures(helpers.copy_asset("mp3", folder / "01.mp3"))

    library, scanner = _setup(tmp_path)
    scanner.scan_folder(folder)

    track = library.list_tracks()[0]
    assert track["cover_hash"]
    thumb = ThumbCache(tmp_path / "thumbs").find(track["cover_hash"], 320)
    assert thumb is not None and thumb.stat().st_size > 0
    library.close()


def test_thumbnail_ensure_is_idempotent(tmp_path: Path) -> None:
    cache = ThumbCache(tmp_path / "thumbs")
    data = helpers.jpeg((10, 20, 30))

    first_hash, first = cache.ensure(data, 320)
    mtime = first.stat().st_mtime
    second_hash, second = cache.ensure(data, 320)

    assert first_hash == second_hash
    assert first == second
    assert second.stat().st_mtime == mtime
