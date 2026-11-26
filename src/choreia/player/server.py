"""Local HTTP server: UI, media with Range, thumbnails, JSON API."""

from __future__ import annotations

import base64
import io
import json
import mimetypes
import os
import re
import secrets
import subprocess
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from ..library.db import Library
from ..library.scanner import Scanner, refresh_track
from ..library.thumbs import ThumbCache
from ..core import clean_file, inspect_file
from ..model import make_picture

AUDIO_TYPES = {
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".m4b": "audio/mp4",
    ".mp4": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
}

CHUNK = 256 * 1024
LRC_PATTERN = re.compile(r"\[(\d{1,3}):(\d{1,2}(?:[.,]\d{1,3})?)\]")


def split_lyrics(text: str) -> tuple[str, str | None]:
    """Return plain lyrics and the original LRC text when it carries timestamps."""
    stripped = text.strip()
    timed = bool(LRC_PATTERN.search(stripped))
    plain = "\n".join(LRC_PATTERN.sub("", line).strip() for line in stripped.splitlines()).strip()
    return plain or stripped, (stripped if timed else None)


class ScanState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running = False
        self.done = 0
        self.total = 0
        self.result: dict | None = None
        self.error: str | None = None

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "running": self.running,
                "done": self.done,
                "total": self.total,
                "result": self.result,
                "error": self.error,
            }


class AppContext:
    def __init__(self, library: Library, thumbs: ThumbCache, web_root: Path) -> None:
        self.library = library
        self.thumbs = thumbs
        self.web_root = Path(web_root)
        self.token = secrets.token_urlsafe(18)
        self.scan = ScanState()
        self._last_prune = 0.0
        self.covers: dict[str, str] = {}

    def maybe_prune(self) -> None:
        """Drop rows for files deleted outside the app, at most every 20 seconds."""
        import time

        now = time.monotonic()
        if now - self._last_prune < 20:
            return
        self._last_prune = now
        try:
            self.library.prune_missing()
        except Exception:
            pass

    # ------------------------------------------------------------------ scan
    def start_scan(self, folder: Path | str) -> bool:
        with self.scan.lock:
            if self.scan.running:
                return False
            self.scan.running = True
            self.scan.done = 0
            self.scan.total = 0
            self.scan.result = None
            self.scan.error = None

        def progress(done: int, total: int) -> None:
            with self.scan.lock:
                self.scan.done = done
                self.scan.total = total

        def work() -> None:
            try:
                scanner = Scanner(self.library, self.thumbs, progress=progress)
                result = scanner.scan_folder(folder)
                with self.scan.lock:
                    self.scan.result = result.as_dict()
            except Exception as exc:  # report, do not crash the worker
                with self.scan.lock:
                    self.scan.error = str(exc)
            finally:
                with self.scan.lock:
                    self.scan.running = False

        threading.Thread(target=work, name="choreia-scan", daemon=True).start()
        return True


class Handler(BaseHTTPRequestHandler):
    server_version = "Choreia/1.0"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------- utilities
    @property
    def context(self) -> AppContext:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        # Keep the console clean; errors still reach the UI through responses.
        pass

    def _query(self) -> dict[str, list[str]]:
        return parse_qs(urlparse(self.path).query)

    def _authorised(self) -> bool:
        token = self.headers.get("X-Token")
        if not token:
            values = self._query().get("t")
            token = values[0] if values else None
        return token == self.context.token

    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length) or b"{}")

    def _file(self, path: Path, content_type: str | None = None, cache: str = "no-store") -> None:
        try:
            size = path.stat().st_size
        except OSError:
            self._error(404, "not found")
            return

        range_header = self.headers.get("Range")
        start, end = 0, size - 1
        status = HTTPStatus.OK
        if range_header:
            match = re.match(r"bytes=(\d*)-(\d*)$", range_header.strip())
            if match:
                first, last = match.groups()
                if first:
                    start = int(first)
                    end = int(last) if last else size - 1
                elif last:
                    start = max(0, size - int(last))
                end = min(end, size - 1)
                if start > end or start >= size:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = HTTPStatus.PARTIAL_CONTENT

        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", cache)
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()

        if self.command == "HEAD":
            return
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                block = handle.read(min(CHUNK, remaining))
                if not block:
                    break
                self.wfile.write(block)
                remaining -= len(block)

    # ---------------------------------------------------------------- routes
    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = self._query()

        if path == "/":
            if not self._authorised():
                self._error(403, "token required")
                return
            index = self.context.web_root / "index.html"
            if not index.exists():
                self._error(404, "ui not found")
                return
            self._file(index, "text/html; charset=utf-8")
            return

        if path.startswith("/static/"):
            candidate = (self.context.web_root / path[len("/static/") :]).resolve()
            root = self.context.web_root.resolve()
            if root not in candidate.parents and candidate != root:
                self._error(403, "forbidden")
                return
            cache = "no-store"
            self._file(candidate, cache=cache)
            return

        if path.startswith("/thumb/"):
            self._serve_thumb(path[len("/thumb/") :], query)
            return

        if path.startswith("/media/"):
            self._serve_media(path[len("/media/") :])
            return

        if path.startswith("/api/"):
            if not self._authorised():
                self._error(403, "token required")
                return
            self._api(path[len("/api/") :], query)
            return

        self._error(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorised():
            self._error(403, "token required")
            return
        path = unquote(urlparse(self.path).path)

        track_match = re.match(r"^/api/tracks/(\d+)$", path)
        if track_match:
            self._update_track(int(track_match.group(1)))
            return

        lyrics_match = re.match(r"^/api/lyrics/(\d+)$", path)
        if lyrics_match:
            self._save_lyrics(int(lyrics_match.group(1)))
            return

        lyrics_fetch = re.match(r"^/api/lyrics/(\d+)/fetch$", path)
        if lyrics_fetch:
            self._fetch_lyrics(int(lyrics_fetch.group(1)))
            return

        if path == "/api/playlists":
            payload = self._read_json()
            name = str(payload.get("name", "")).strip()
            if not name:
                self._error(400, "name required")
                return
            import sqlite3

            try:
                playlist_id = self.context.library.create_playlist(name)
            except sqlite3.IntegrityError:
                self._error(409, "playlist exists")
                return
            self._json({"id": playlist_id, "name": name})
            return

        playlist_track = re.match(r"^/api/playlists/(\d+)/tracks$", path)
        if playlist_track:
            payload = self._read_json()
            playlist_id = int(playlist_track.group(1))
            track_id = int(payload.get("track_id") or 0)
            if self.context.library.playlist(playlist_id) is None:
                self._error(404, "no playlist")
                return
            if self.context.library.track(track_id) is None:
                self._error(404, "no track")
                return
            position = self.context.library.add_to_playlist(playlist_id, track_id)
            self._json({"ok": True, "position": position})
            return

        if path == "/api/pick-folder":
            from .dialogs import pick_folder

            self._json({"path": pick_folder()})
            return

        if path == "/api/pick-files":
            from .dialogs import pick_files

            self._json({"paths": pick_files()})
            return

        if path == "/api/mkdir":
            payload = self._read_json()
            target = Path(str(payload.get("path", "")).strip())
            if not target.name or target.name in (".", ".."):
                self._error(400, "name required")
                return
            parent = target.parent
            if not parent.is_dir():
                self._error(404, "parent folder not found")
                return
            roots = [
                os.path.normpath(folder["path"]).lower() for folder in self.context.library.folders()
            ]
            parent_key = os.path.normpath(str(parent)).lower()
            inside = any(parent_key == root or parent_key.startswith(root + "\\") for root in roots)
            if not inside:
                self._error(403, "outside the library")
                return
            try:
                target.mkdir()
            except FileExistsError:
                self._error(409, "folder exists")
                return
            except OSError as exc:
                self._error(500, str(exc))
                return
            self._json({"path": str(target)})
            return

        if path == "/api/delete-tracks":
            from .dialogs import recycle

            payload = self._read_json()
            ids = [int(value) for value in (payload.get("ids") or [])][:500]
            library = self.context.library
            roots = [
                os.path.normpath(folder["path"]).lower() for folder in library.folders()
            ]
            removed = 0
            for track_id in ids:
                track = library.track(track_id)
                if track is None:
                    continue
                target = Path(track["path"])
                key = os.path.normpath(str(target)).lower()
                inside = any(key.startswith(root + "\\") for root in roots)
                if not inside:
                    continue
                if target.exists() and not recycle(target):
                    continue
                library.delete_tracks([str(target)])
                removed += 1
            self._json({"removed": removed})
            return

        if path == "/api/upload":
            from ..library.scanner import AUDIO_SUFFIXES

            directory = Path((self._query().get("path") or [""])[0])
            if not directory.is_dir():
                self._error(404, "folder not found")
                return
            roots = [
                os.path.normpath(folder["path"]).lower() for folder in self.context.library.folders()
            ]
            key = os.path.normpath(str(directory)).lower()
            if not any(key == root or key.startswith(root + "\\") for root in roots):
                self._error(403, "outside the library")
                return

            raw_name = unquote(self.headers.get("X-Filename", "") or "")
            safe_name = Path(raw_name).name
            suffix = Path(safe_name).suffix.lower()
            if not safe_name or suffix not in AUDIO_SUFFIXES:
                self._error(400, "unsupported audio file")
                return

            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > 300_000_000:
                self._error(400, "bad size")
                return

            target = directory / safe_name
            counter = 1
            while target.exists():
                counter += 1
                target = directory / f"{Path(safe_name).stem} ({counter}){suffix}"

            written = 0
            try:
                with target.open("wb") as handle:
                    while written < length:
                        chunk = self.rfile.read(min(262144, length - written))
                        if not chunk:
                            break
                        handle.write(chunk)
                        written += len(chunk)
            except OSError as exc:
                target.unlink(missing_ok=True)
                self._error(500, str(exc))
                return

            if written != length:
                target.unlink(missing_ok=True)
                self._error(400, "upload interrupted")
                return

            try:
                refresh_track(self.context.library, self.context.thumbs, target)
            except Exception as exc:
                self._error(500, f"cannot index: {exc}")
                return
            self._json({"path": str(target), "name": target.name})
            return

        if path == "/api/add-path":
            from ..library.scanner import AUDIO_SUFFIXES

            payload = self._read_json()
            target = Path(str(payload.get("path", "")).strip())
            if target.is_dir():
                folder_id = self.context.library.add_folder(target)
                started = self.context.start_scan(target)
                self._json({"kind": "folder", "id": folder_id, "started": started})
                return
            if target.is_file() and target.suffix.lower() in AUDIO_SUFFIXES:
                try:
                    refresh_track(self.context.library, self.context.thumbs, target)
                except Exception as exc:
                    self._error(500, f"cannot read: {exc}")
                    return
                self._json({"kind": "file", "added": 1})
                return
            self._error(404, "path not found")
            return

        if path == "/api/add-files":
            from ..library.scanner import AUDIO_SUFFIXES

            payload = self._read_json()
            raw_paths = payload.get("paths") or []
            added = 0
            for raw in raw_paths[:500]:
                candidate = Path(str(raw))
                if not candidate.is_file() or candidate.suffix.lower() not in AUDIO_SUFFIXES:
                    continue
                try:
                    refresh_track(self.context.library, self.context.thumbs, candidate)
                    added += 1
                except Exception:
                    continue
            self._json({"added": added})
            return

        if path == "/api/reveal":
            payload = self._read_json()
            target = Path(str(payload.get("path", "")))
            if not target.exists():
                self._error(404, "not found")
                return
            if target.is_dir():
                subprocess.run(["explorer", str(target)], check=False)
            else:
                subprocess.run(["explorer", "/select,", str(target)], check=False)
            self._json({"ok": True})
            return

        if path == "/api/folders":
            payload = self._read_json()
            folder = Path(payload.get("path", ""))
            if not folder.is_dir():
                self._error(400, "not a directory")
                return
            folder_id = self.context.library.add_folder(folder)
            self._json({"id": folder_id, "path": str(folder)})
            return
        if path == "/api/scan":
            payload = self._read_json()
            folder = payload.get("path")
            if not folder:
                self._error(400, "path required")
                return
            started = self.context.start_scan(folder)
            self._json({"started": started})
            return
        if path == "/api/settings":
            payload = self._read_json()
            key = payload.get("key")
            if not key:
                self._error(400, "key required")
                return
            self.context.library.set_setting(str(key), str(payload.get("value", "")))
            self._json({"ok": True})
            return
        self._error(404, "not found")

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._authorised():
            self._error(403, "token required")
            return
        path = unquote(urlparse(self.path).path)
        match = re.match(r"^/api/folders/(\d+)$", path)
        if match:
            removed = self.context.library.remove_folder(int(match.group(1)))
            self._json({"ok": True, "removed": removed})
            return
        lyrics_match = re.match(r"^/api/lyrics/(\d+)$", path)
        if lyrics_match:
            self.context.library.delete_lyrics(int(lyrics_match.group(1)))
            self._json({"ok": True})
            return

        playlist_match = re.match(r"^/api/playlists/(\d+)/tracks/(\d+)$", path)
        if playlist_match:
            self.context.library.remove_from_playlist(
                int(playlist_match.group(1)), int(playlist_match.group(2))
            )
            self._json({"ok": True})
            return

        playlist_match = re.match(r"^/api/playlists/(\d+)$", path)
        if playlist_match:
            self.context.library.delete_playlist(int(playlist_match.group(1)))
            self._json({"ok": True})
            return
        self._error(404, "not found")

    # ----------------------------------------------------------------- parts
    def _update_track(self, track_id: int) -> None:
        from pathlib import Path

        library = self.context.library
        track = library.track(track_id)
        if track is None:
            self._error(404, "no track")
            return
        source = Path(track["path"])
        if not source.exists():
            self._error(404, "file missing")
            return
        payload = self._read_json()
        current = inspect_file(source)
        names = ("title", "artist", "album", "album_artist", "track", "disc", "year", "genre")
        metadata = {
            name: str(payload.get(name, current.fields.get(name, ""))) for name in names
        }

        action = str(payload.get("cover_action") or "keep")
        keep = current.front_cover
        if action == "remove":
            keep = None
        elif action == "set":
            raw = str(payload.get("cover") or "")
            if not raw:
                self._error(400, "cover data required")
                return
            try:
                data = base64.b64decode(raw.split(",")[-1])
            except Exception:
                self._error(400, "bad cover data")
                return
            if len(data) > 12_000_000:
                self._error(413, "cover too large")
                return
            try:
                from PIL import Image

                with Image.open(io.BytesIO(data)) as probe:
                    probe.verify()
            except Exception:
                self._error(400, "not an image")
                return
            keep = make_picture(0, data, type=3, desc="Cover", source="file")

        try:
            clean_file(source, keep=keep, metadata=metadata)
            updated = refresh_track(library, self.context.thumbs, source)
        except Exception as exc:
            self._error(500, f"cannot write: {exc}")
            return

        album_updated = 0
        if action == "set" and payload.get("apply_to_album") and metadata["album"].strip():
            for other in library.album_tracks(metadata["album"], metadata.get("album_artist", "")):
                if other["path"] == str(source):
                    continue
                other_path = Path(other["path"])
                if not other_path.exists():
                    continue
                try:
                    other_report = inspect_file(other_path)
                    clean_file(other_path, keep=keep, metadata=other_report.fields)
                    refresh_track(library, self.context.thumbs, other_path)
                    album_updated += 1
                except Exception:
                    continue

        self._json({"track": updated, "album_updated": album_updated})

    def _fetch_lyrics(self, track_id: int) -> None:
        from ..sources.lyrics import lookup

        library = self.context.library
        track = library.track(track_id)
        if track is None:
            self._error(404, "no track")
            return
        found = lookup(
            str(track["artist"] or ""),
            str(track["title"] or ""),
            str(track["album"] or ""),
            float(track["duration"] or 0),
        )
        if not found:
            self._error(404, "lyrics not found")
            return
        plain = str(found.get("plain") or "")
        synced = found.get("synced")
        if not plain and synced:
            plain, _ = split_lyrics(synced)
        library.set_lyrics(
            track_id,
            plain=plain,
            synced=synced,
            source="lrclib",
            instrumental=bool(found.get("instrumental")),
        )
        self._json({"lyrics": library.lyrics(track_id)})

    def _save_lyrics(self, track_id: int) -> None:
        library = self.context.library
        if library.track(track_id) is None:
            self._error(404, "no track")
            return
        body = self._read_json()
        text = str(body.get("text", ""))
        if not text.strip():
            library.delete_lyrics(track_id)
            self._json({"ok": True, "deleted": True})
            return
        plain, synced = split_lyrics(text)
        library.set_lyrics(track_id, plain=plain, synced=synced)
        self._json({"lyrics": library.lyrics(track_id)})

    def _api(self, route: str, query: dict[str, list[str]]) -> None:
        library = self.context.library
        if route == "browse":
            import os

            self.context.maybe_prune()
            directory = (query.get("path") or [""])[0]
            if not directory:
                self._error(400, "path required")
                return
            normalized = os.path.normpath(directory)
            roots = [os.path.normpath(folder["path"]) for folder in library.folders()]
            lowered = normalized.lower()
            inside = any(
                lowered == root.lower() or lowered.startswith(root.lower() + "\\") for root in roots
            )
            if not inside:
                self._error(403, "outside the library")
                return
            self._json(library.browse(normalized))
            return
        if route == "cover-search":
            from ..sources.covers import search as search_covers

            artist = (query.get("artist") or [""])[0]
            album = (query.get("album") or [""])[0]
            title = (query.get("title") or [""])[0]
            token = library.setting("genius_token") or ""
            try:
                found = search_covers(artist, album, title, token)
            except Exception:
                found = []
            results = []
            for item in found:
                key = secrets.token_urlsafe(8)
                if len(self.context.covers) > 40:
                    self.context.covers.pop(next(iter(self.context.covers)), None)
                self.context.covers[key] = item["cover"]
                results.append(
                    {
                        "key": key,
                        "source": item["source"],
                        "label": item["label"],
                        "artist": item["artist"],
                        "thumb": item["thumb"],
                    }
                )
            self._json({"results": results})
            return
        cover_match = re.match(r"^cover/([A-Za-z0-9_-]+)$", route)
        if cover_match:
            stored = self.context.covers.get(cover_match.group(1))
            if stored is None:
                self._error(404, "no cover")
                return
            self._json({"cover": stored})
            return
        if route == "albums":
            self._json({"albums": library.albums()})
            return
        track_match = re.match(r"^tracks/(\d+)$", route)
        if track_match:
            track = library.track(int(track_match.group(1)))
            if track is None:
                self._error(404, "no track")
                return
            self._json({"track": track})
            return
        if route == "albums/tracks":
            album = (query.get("album") or [""])[0]
            artist = (query.get("artist") or [""])[0]
            self._json({"tracks": library.album_tracks(album, artist)})
            return
        if route == "playlists":
            self._json({"playlists": library.playlists()})
            return
        playlist_match = re.match(r"^playlists/(\d+)$", route)
        if playlist_match:
            playlist_id = int(playlist_match.group(1))
            playlist = library.playlist(playlist_id)
            if playlist is None:
                self._error(404, "no playlist")
                return
            self._json({"playlist": playlist, "tracks": library.playlist_tracks(playlist_id)})
            return
        if route.startswith("lyrics/"):
            raw_id = route.split("/", 1)[1]
            if not raw_id.isdigit():
                self._error(400, "bad id")
                return
            payload = library.lyrics(int(raw_id))
            self._json({"lyrics": payload})
            return
        if route == "tracks":
            self.context.maybe_prune()
            sort = (query.get("sort") or ["artist"])[0]
            search = (query.get("q") or [""])[0]
            limit = min(int((query.get("limit") or ["500"])[0]), 2000)
            offset = max(int((query.get("offset") or ["0"])[0]), 0)
            tracks = library.list_tracks(sort=sort, query=search, limit=limit, offset=offset)
            self._json({"total": library.count_tracks(search), "tracks": tracks})
            return
        if route == "folders":
            self._json({"folders": library.folders()})
            return
        if route == "scan/status":
            self._json(self.context.scan.snapshot())
            return
        if route == "settings":
            key = (query.get("key") or [""])[0]
            if key:
                self._json({"key": key, "value": library.setting(key)})
            else:
                self._json({"ok": True})
            return
        self._error(404, "unknown api route")

    def _serve_thumb(self, digest: str, query: dict[str, list[str]]) -> None:
        size = int((query.get("size") or ["320"])[0])
        path = self.context.thumbs.find(digest, size)
        if path is None:
            self._error(404, "no thumbnail")
            return
        self._file(path, "image/jpeg", cache="public, max-age=31536000")

    def _serve_media(self, raw_id: str) -> None:
        if not self._authorised():
            self._error(403, "token required")
            return
        track_id = raw_id.split(".")[0]
        if not track_id.isdigit():
            self._error(400, "bad id")
            return
        track = self.context.library.track(int(track_id))
        if track is None:
            self._error(404, "no track")
            return
        path = Path(track["path"])
        if not path.exists():
            self._error(404, "file missing")
            return
        self._file(path, AUDIO_TYPES.get(path.suffix.lower()), cache="no-store")


class QuietServer(ThreadingHTTPServer):
    """Do not print tracebacks when a client hangs up mid-request."""

    def handle_error(self, request, client_address):  # noqa: ANN001
        import sys

        error = sys.exc_info()[1]
        if isinstance(error, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


class Server:
    def __init__(
        self,
        library: Library,
        thumbs: ThumbCache,
        web_root: Path,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        self.context = AppContext(library, thumbs, web_root)
        self.httpd = QuietServer((host, port), Handler)
        self.httpd.app = self.context  # type: ignore[attr-defined]
        self.thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?t={self.context.token}"

    def start(self) -> "Server":
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="choreia-http", daemon=True)
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
