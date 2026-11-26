"""SQLite library index: tracks, folders, playlists, lyrics, settings."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1

TRACK_COLUMNS = (
    "path",
    "folder_id",
    "title",
    "artist",
    "album",
    "album_artist",
    "track_no",
    "disc_no",
    "year",
    "genre",
    "duration",
    "bitrate",
    "sample_rate",
    "channels",
    "size",
    "mtime",
    "cover_hash",
)

SORTS = {
    "title": "title COLLATE NOCASE, artist COLLATE NOCASE",
    "artist": "artist COLLATE NOCASE, album COLLATE NOCASE, disc_no, track_no",
    "album": "album COLLATE NOCASE, disc_no, track_no, title COLLATE NOCASE",
    "duration": "duration DESC",
    "added": "added_at DESC",
    "played": "COALESCE(last_played, 0) DESC",
    "year": "COALESCE(year, '') DESC, album COLLATE NOCASE, track_no",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    added_at REAL NOT NULL,
    last_scan_at REAL
);

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    title TEXT NOT NULL DEFAULT '',
    artist TEXT NOT NULL DEFAULT '',
    album TEXT NOT NULL DEFAULT '',
    album_artist TEXT NOT NULL DEFAULT '',
    track_no INTEGER,
    disc_no INTEGER,
    year TEXT NOT NULL DEFAULT '',
    genre TEXT NOT NULL DEFAULT '',
    duration REAL NOT NULL DEFAULT 0,
    bitrate INTEGER NOT NULL DEFAULT 0,
    sample_rate INTEGER NOT NULL DEFAULT 0,
    channels INTEGER NOT NULL DEFAULT 0,
    size INTEGER NOT NULL DEFAULT 0,
    mtime REAL NOT NULL DEFAULT 0,
    cover_hash TEXT,
    added_at REAL NOT NULL,
    play_count INTEGER NOT NULL DEFAULT 0,
    last_played REAL
);

CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tracks_folder ON tracks(folder_id);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    PRIMARY KEY (playlist_id, position)
);

CREATE TABLE IF NOT EXISTS lyrics (
    track_id INTEGER PRIMARY KEY REFERENCES tracks(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    synced TEXT,
    plain TEXT,
    instrumental INTEGER NOT NULL DEFAULT 0,
    fetched_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class Library:
    """Thread-safe wrapper around one SQLite connection."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=2.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout=2000")
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    # ------------------------------------------------------------- lifecycle
    def _migrate(self) -> None:
        with self._lock:
            version = self._conn.execute("PRAGMA user_version").fetchone()[0]
            if version < SCHEMA_VERSION:
                self._conn.executescript(SCHEMA)
                self._conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "Library":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ---------------------------------------------------------------- tracks
    def upsert_track(self, **values: Any) -> int:
        row = {column: values.get(column) for column in TRACK_COLUMNS}
        if not row["path"]:
            raise ValueError("path is required")
        for numeric in ("track_no", "disc_no"):
            row[numeric] = int(row[numeric]) if row[numeric] not in (None, "") else None
        for numeric in ("duration", "bitrate", "sample_rate", "channels", "size", "mtime"):
            row[numeric] = float(row[numeric] or 0)
        row["folder_id"] = int(row["folder_id"]) if row["folder_id"] is not None else None
        for text in ("title", "artist", "album", "album_artist", "year", "genre", "cover_hash"):
            row[text] = str(row[text] or "")

        columns = ["path", "folder_id", "title", "artist", "album", "album_artist",
                   "track_no", "disc_no", "year", "genre", "duration", "bitrate",
                   "sample_rate", "channels", "size", "mtime", "cover_hash"]
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "path")
        sql = (
            f"INSERT INTO tracks ({', '.join(columns)}, added_at) "
            f"VALUES ({placeholders}, ?) "
            f"ON CONFLICT(path) DO UPDATE SET {updates}"
        )
        params = [row[column] for column in columns] + [values.get("added_at") or 0]
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()
            existing = self._conn.execute("SELECT id FROM tracks WHERE path=?", (row["path"],)).fetchone()
            return int(existing["id"]) if existing else 0

    def track(self, track_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
        return dict(row) if row else None

    def track_by_path(self, path: Path | str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tracks WHERE path=?", (str(path),)).fetchone()
        return dict(row) if row else None

    def list_tracks(
        self,
        *,
        sort: str = "artist",
        query: str = "",
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict]:
        where, params = self._filter(query)
        order = SORTS.get(sort, SORTS["artist"])
        sql = f"SELECT * FROM tracks {where} ORDER BY {order} LIMIT ? OFFSET ?"
        with self._lock:
            rows = self._conn.execute(sql, (*params, limit, offset)).fetchall()
        return [dict(row) for row in rows]

    def count_tracks(self, query: str = "") -> int:
        where, params = self._filter(query)
        with self._lock:
            row = self._conn.execute(f"SELECT COUNT(*) AS total FROM tracks {where}", params).fetchone()
        return int(row["total"])

    @staticmethod
    def _filter(query: str) -> tuple[str, list[Any]]:
        if not query.strip():
            return "", []
        like = f"%{query.strip()}%"
        return (
            "WHERE (title LIKE ? OR artist LIKE ? OR album LIKE ? OR path LIKE ?)",
            [like, like, like, like],
        )

    def mark_played(self, track_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE tracks SET play_count=play_count+1, last_played=strftime('%s','now') WHERE id=?",
                (track_id,),
            )
            self._conn.commit()

    def browse(self, directory: str) -> dict:
        """List immediate subfolders and the tracks that sit directly in `directory`."""
        import os

        directory = os.path.normpath(directory)
        prefix = directory.rstrip("\\/") + "\\"
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM tracks WHERE path LIKE ? ORDER BY path COLLATE NOCASE",
                (prefix + "%",),
            ).fetchall()

        folders: dict[str, int] = {}
        tracks: list[dict] = []
        for row in rows:
            rest = str(row["path"])[len(prefix):]
            if "\\" in rest or "/" in rest:
                name = rest.replace("/", "\\").split("\\", 1)[0]
                folders[name] = folders.get(name, 0) + 1
            else:
                tracks.append(dict(row))

        # Real subdirectories, including ones with no indexed tracks yet.
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir() and not entry.name.startswith("."):
                            folders.setdefault(entry.name, 0)
                    except OSError:
                        continue
        except OSError:
            pass

        # Cheap change detector: the client re-renders the folder only when it differs,
        # so an unchanged folder is never repainted and cannot flicker.
        import hashlib

        signature = hashlib.sha1(
            "\n".join(
                [f"f:{name}" for name in sorted(folders)]
                + [
                    "t:{}:{}:{}:{}:{}:{}".format(
                        row["id"],
                        row["path"],
                        row["title"],
                        row["artist"],
                        row["album"],
                        row["duration"],
                    )
                    for row in tracks
                ]
            ).encode("utf-8")
        ).hexdigest()

        return {
            "path": directory,
            "folders": [
                {"name": name, "path": prefix + name, "tracks": count}
                for name, count in sorted(folders.items(), key=lambda item: item[0].lower())
            ],
            "tracks": tracks,
            "signature": signature,
        }

    def album_tracks(self, album: str, album_artist: str = "") -> list[dict]:
        if not album.strip():
            return []
        sql = "SELECT * FROM tracks WHERE album = ? COLLATE NOCASE"
        params: list = [album]
        if album_artist.strip():
            sql += " AND album_artist = ? COLLATE NOCASE"
            params.append(album_artist)
        sql += " ORDER BY disc_no, track_no, title COLLATE NOCASE"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def albums(self) -> list[dict]:
        from collections import Counter

        markers = ("feat", "ft.", "&", ",", " x ")

        def primary_artist(rows: list) -> str:
            named = [row["album_artist"] for row in rows if str(row["album_artist"] or "").strip()]
            if named:
                return Counter(named).most_common(1)[0][0]
            solo = [
                row["artist"]
                for row in rows
                if str(row["artist"] or "").strip()
                and not any(marker in str(row["artist"]).lower() for marker in markers)
            ]
            pool = solo or [row["artist"] for row in rows if str(row["artist"] or "").strip()]
            return Counter(pool).most_common(1)[0][0] if pool else ""

        with self._lock:
            groups = self._conn.execute(
                "SELECT album, COUNT(*) AS tracks FROM tracks WHERE album != '' "
                "GROUP BY album COLLATE NOCASE ORDER BY album COLLATE NOCASE"
            ).fetchall()
            albums = []
            for group in groups:
                tracks = self._conn.execute(
                    "SELECT id, artist, album_artist, cover_hash FROM tracks "
                    "WHERE album = ? COLLATE NOCASE "
                    "ORDER BY COALESCE(disc_no, 0), COALESCE(track_no, 0), title COLLATE NOCASE",
                    (group["album"],),
                ).fetchall()
                # The grid shows the first track that has art, and the album-cover
                # dialog rewrites exactly that file.
                cover = next((row for row in tracks if row["cover_hash"]), tracks[0] if tracks else None)
                albums.append(
                    {
                        "album": group["album"],
                        "album_artist": primary_artist(list(tracks)),
                        "tracks": group["tracks"],
                        "cover_hash": cover["cover_hash"] if cover else "",
                        "cover_track_id": int(cover["id"]) if cover else None,
                    }
                )
        return albums

    def tracks_under(self, folder_path: str) -> Iterable[dict]:
        prefix = folder_path.rstrip("\\/") + "%"
        with self._lock:
            rows = self._conn.execute("SELECT * FROM tracks WHERE path LIKE ?", (prefix,)).fetchall()
        return [dict(row) for row in rows]

    def prune_missing(self) -> int:
        """Drop index rows whose files are gone, so deleting a file updates the UI."""
        with self._lock:
            rows = self._conn.execute("SELECT path FROM tracks").fetchall()
        missing = [row["path"] for row in rows if not Path(row["path"]).exists()]
        if missing:
            self.delete_tracks(missing)
        return len(missing)

    def delete_tracks(self, paths: Iterable[str]) -> int:
        paths = list(paths)
        if not paths:
            return 0
        with self._lock:
            cursor = self._conn.executemany("DELETE FROM tracks WHERE path=?", [(path,) for path in paths])
            self._conn.commit()
        return cursor.rowcount

    # --------------------------------------------------------------- folders
    def add_folder(self, path: Path | str) -> int:
        import time

        with self._lock:
            self._conn.execute(
                "INSERT INTO folders (path, added_at) VALUES (?, ?) ON CONFLICT(path) DO NOTHING",
                (str(path), time.time()),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT id FROM folders WHERE path=?", (str(path),)).fetchone()
        return int(row["id"]) if row else 0

    def folders(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM folders ORDER BY path COLLATE NOCASE").fetchall()
        return [dict(row) for row in rows]

    def remove_folder(self, folder_id: int) -> int:
        """Forget a folder, keeping tracks that still belong to another library root."""
        with self._lock:
            row = self._conn.execute("SELECT path FROM folders WHERE id=?", (folder_id,)).fetchone()
            if row is None:
                return 0
            prefix = str(row["path"]).rstrip("\\/") + "\\"
            remaining = self._conn.execute(
                "SELECT id, path FROM folders WHERE id<>?", (folder_id,)
            ).fetchall()
            roots = [
                (int(item["id"]), str(item["path"]).rstrip("\\/") + "\\") for item in remaining
            ]
            rows = self._conn.execute(
                "SELECT id, path FROM tracks WHERE path LIKE ?", (prefix + "%",)
            ).fetchall()

            kept: list[tuple[int, int]] = []
            for track in rows:
                lowered = str(track["path"]).lower()
                owner: tuple[int, int] | None = None
                for root_id, root_prefix in roots:
                    root_lower = root_prefix.lower()
                    if lowered.startswith(root_lower) and (owner is None or len(root_prefix) > owner[1]):
                        owner = (root_id, len(root_prefix))
                if owner is not None:
                    kept.append((int(track["id"]), owner[0]))
                else:
                    self._conn.execute("DELETE FROM tracks WHERE id=?", (int(track["id"]),))
            for track_id, root_id in kept:
                self._conn.execute(
                    "UPDATE tracks SET folder_id=? WHERE id=?", (root_id, track_id)
                )
            self._conn.execute("DELETE FROM folders WHERE id=?", (folder_id,))
            self._conn.commit()
        return len(rows) - len(kept)

    # ---------------------------------------------------------------- lyrics
    def lyrics(self, track_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM lyrics WHERE track_id=?", (track_id,)).fetchone()
        return dict(row) if row else None

    def set_lyrics(
        self,
        track_id: int,
        *,
        plain: str,
        synced: str | None = None,
        source: str = "manual",
        instrumental: bool = False,
    ) -> None:
        import time

        with self._lock:
            self._conn.execute(
                "INSERT INTO lyrics (track_id, source, synced, plain, instrumental, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(track_id) DO UPDATE SET source=excluded.source, synced=excluded.synced, "
                "plain=excluded.plain, instrumental=excluded.instrumental, fetched_at=excluded.fetched_at",
                (track_id, source, synced, plain, 1 if instrumental else 0, time.time()),
            )
            self._conn.commit()

    def delete_lyrics(self, track_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM lyrics WHERE track_id=?", (track_id,))
            self._conn.commit()

    # ------------------------------------------------------------- playlists
    def playlists(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT p.id, p.name, p.created_at, COUNT(pt.track_id) AS tracks "
                "FROM playlists p LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id "
                "GROUP BY p.id ORDER BY p.name COLLATE NOCASE"
            ).fetchall()
        return [dict(row) for row in rows]

    def playlist(self, playlist_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM playlists WHERE id=?", (playlist_id,)).fetchone()
        return dict(row) if row else None

    def create_playlist(self, name: str) -> int:
        with self._lock:
            self._conn.execute(
                "INSERT INTO playlists (name, created_at) VALUES (?, strftime('%s','now'))", (name,)
            )
            self._conn.commit()
            row = self._conn.execute("SELECT id FROM playlists WHERE name=?", (name,)).fetchone()
        return int(row["id"]) if row else 0

    def delete_playlist(self, playlist_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
            self._conn.commit()

    def playlist_tracks(self, playlist_id: int) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT t.*, pt.position FROM playlist_tracks pt "
                "JOIN tracks t ON t.id = pt.track_id "
                "WHERE pt.playlist_id = ? ORDER BY pt.position",
                (playlist_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_to_playlist(self, playlist_id: int, track_id: int) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(position) + 1, 0) AS pos FROM playlist_tracks WHERE playlist_id=?",
                (playlist_id,),
            ).fetchone()
            position = int(row["pos"])
            self._conn.execute(
                "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
                (playlist_id, track_id, position),
            )
            self._conn.commit()
        return position

    def remove_from_playlist(self, playlist_id: int, position: int) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id=? AND position=?",
                (playlist_id, position),
            )
            self._conn.execute(
                "UPDATE playlist_tracks SET position = position - 1 "
                "WHERE playlist_id=? AND position > ?",
                (playlist_id, position),
            )
            self._conn.commit()

    # -------------------------------------------------------------- settings
    def setting(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def settings_with_prefix(self, prefix: str) -> dict[str, str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value FROM settings WHERE key LIKE ?", (prefix + "%",)
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            self._conn.commit()
