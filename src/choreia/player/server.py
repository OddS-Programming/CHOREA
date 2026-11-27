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
from urllib import request as urlrequest
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
UPDATE_REPO = "OddS-Programming/CHOREA"
LRC_PATTERN = re.compile(r"\[(\d{1,3}):(\d{1,2}(?:[.,]\d{1,3})?)\]")


def version_tuple(value: str) -> tuple[int, ...]:
    parts = [int(piece) for piece in re.findall(r"\d+", value or "")[:3]]
    return tuple(parts) if parts else (0,)


def latest_release() -> dict:
    request = urlrequest.Request(
        f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest",
        headers={
            "User-Agent": "Choreia/1.0",
            "Accept": "application/vnd.github+json",
        },
    )
    with urlrequest.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def open_shared(path: Path):
    """Open a file for reading without blocking a later rename on Windows.

    Playback streams the current file over HTTP. With a plain open() Windows keeps
    the target locked, so saving fresh tags over the playing track fails with
    WinError 5; FILE_SHARE_DELETE lets os.replace swap the file while the stream
    keeps reading the old contents.
    """
    if os.name != "nt":
        return open(path, "rb")
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.restype = wintypes.HANDLE
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        generic_read = 0x80000000
        share_read_write_delete = 0x1 | 0x2 | 0x4
        open_existing = 3
        attribute_normal = 0x80
        handle = create_file(
            str(path),
            generic_read,
            share_read_write_delete,
            None,
            open_existing,
            attribute_normal,
            None,
        )
        invalid = ctypes.c_void_p(-1).value
        if handle is None or handle == invalid:
            return open(path, "rb")
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        return os.fdopen(descriptor, "rb")
    except (ImportError, OSError, ValueError):
        return open(path, "rb")


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
        self._scan_thread: threading.Thread | None = None
        self._last_prune = 0.0
        self.covers: dict[str, str] = {}
        self.genius_check: tuple[float, str] | None = None
        self.online_jobs: dict[str, dict] = {}
        self.online_lock = threading.Lock()

    def genius_state(self) -> str:
        token = self.library.setting("genius_token") or ""
        if not token:
            self.genius_check = None
            return "none"
        import time

        if self.genius_check and time.monotonic() - self.genius_check[0] < 300:
            return self.genius_check[1]
        from ..sources.covers import check_token

        try:
            state = "ok" if check_token(token) else "invalid"
        except Exception:
            state = "error"
        self.genius_check = (time.monotonic(), state)
        return state

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
                worker = self._scan_thread
                if worker is not None and not worker.is_alive():
                    # A worker vanished without clearing the flag; recover instead of
                    # refusing to scan until the next launch.
                    self.scan.running = False
                    self.scan.error = None
                else:
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

        thread = threading.Thread(target=work, name="choreia-scan", daemon=True)
        try:
            thread.start()
        except RuntimeError as exc:  # e.g. the system refused a new thread
            with self.scan.lock:
                self.scan.running = False
                self.scan.error = str(exc)
            return False
        self._scan_thread = thread
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

    def _host_allowed(self) -> bool:
        """Reject foreign Host headers so a rebinding domain cannot reach us."""
        host = (self.headers.get("Host") or "").strip().lower()
        if not host:
            return False
        name = host.rsplit(":", 1)[0] if not host.endswith("]") else host
        return name in {"127.0.0.1", "localhost", "[::1]", "::1"}

    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length) or b"{}"
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Callers validate their required fields and answer with a 400.
            return {}
        return payload if isinstance(payload, dict) else {}

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
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()

        if self.command == "HEAD":
            return
        with open_shared(path) as handle:
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
        if not self._host_allowed():
            self._error(403, "bad host")
            return
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
            if not self._authorised():
                self._error(403, "token required")
                return
            digest = path[len("/thumb/") :]
            if not re.fullmatch(r"[0-9a-fA-F]{40}", digest):
                self._error(400, "bad digest")
                return
            self._serve_thumb(digest, query)
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
        if not self._host_allowed():
            self._error(403, "bad host")
            return
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

        if path == "/api/album-cover":
            self._album_cover()
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

        playlist_move = re.match(r"^/api/playlists/(\d+)/move$", path)
        if playlist_move:
            payload = self._read_json()
            try:
                source = int(payload.get("from"))
                target = int(payload.get("to"))
            except (TypeError, ValueError):
                self._error(400, "from and to are required")
                return
            moved = self.context.library.reorder_playlist(
                int(playlist_move.group(1)), source, target
            )
            self._json({"ok": moved})
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
            payload = self._read_json()
            initial = str(payload.get("initial") or "")
            from .dialogs import pick_folder

            try:
                chosen = pick_folder(initial)
            except Exception as exc:
                self._error(500, str(exc))
                return
            if not chosen:
                self._json({"cancelled": True})
                return
            self._json({"path": chosen})
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

        if path == "/api/update/apply":
            self._update_apply()
            return

        if path == "/api/online/download":
            self._online_download()
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
            key = str(payload.get("key") or "")
            if not key:
                self._error(400, "key required")
                return
            value = str(payload.get("value", ""))
            if key == "genius_token":
                value = value.strip()
                if value:
                    from ..sources.covers import check_token

                    try:
                        accepted = check_token(value)
                    except Exception:
                        self._error(502, "Не удалось проверить токен Genius — нет связи")
                        return
                    if not accepted:
                        self._error(400, "Genius не принял токен (401)")
                        return
                self.context.genius_check = None
            self.context.library.set_setting(key, value)
            self._json({"ok": True})
            return
        self._error(404, "not found")

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._host_allowed():
            self._error(403, "bad host")
            return
        if not self._authorised():
            self._error(403, "token required")
            return
        path = unquote(urlparse(self.path).path)
        match = re.match(r"^/api/folders/(\d+)$", path)
        if match:
            folder_id = int(match.group(1))
            folders = self.context.library.folders()
            target = next((item for item in folders if int(item["id"]) == folder_id), None)
            removed = self.context.library.remove_folder(folder_id)
            rescanning = False
            if target is not None:
                lowered = str(target["path"]).rstrip("\\/").lower() + "\\"
                ancestors = [
                    item
                    for item in self.context.library.folders()
                    if lowered.startswith(str(item["path"]).rstrip("\\/").lower() + "\\")
                ]
                ancestors.sort(key=lambda item: len(str(item["path"])), reverse=True)
                for item in ancestors:
                    if self.context.start_scan(item["path"]):
                        rescanning = True
                        break
            self._json({"ok": True, "removed": removed, "rescanning": rescanning})
            return
        if path == "/api/backups":
            removed = 0
            freed = 0
            for item in self._backup_files():
                try:
                    freed += item.stat().st_size
                    item.unlink()
                    removed += 1
                except OSError:
                    continue
            self._json({"removed": removed, "freed": freed})
            return
        if path == "/api/lyrics":
            removed = self.context.library.clear_lyrics()
            self._json({"removed": removed})
            return
        lyrics_match = re.match(r"^/api/lyrics/(\d+)$", path)
        if lyrics_match:
            self.context.library.delete_lyrics(int(lyrics_match.group(1)))
            self._json({"ok": True})
            return

        if path == "/api/cache":
            root = self.context.thumbs.root
            removed = 0
            freed = 0
            for item in root.glob("*-*.jpg"):
                try:
                    freed += item.stat().st_size
                    item.unlink()
                    removed += 1
                except OSError:
                    continue
            self._json({"removed": removed, "freed": freed})
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
    def _cover_picture(self, raw: str):
        """Validate a data URL and build a front-cover Picture, or raise ValueError."""
        if not raw:
            raise ValueError("cover data required")
        try:
            data = base64.b64decode(raw.split(",")[-1])
        except Exception as exc:
            raise ValueError("bad cover data") from exc
        if len(data) > 12_000_000:
            raise ValueError("cover too large")
        try:
            from PIL import Image

            with Image.open(io.BytesIO(data)) as probe:
                probe.verify()
        except Exception as exc:
            raise ValueError("not an image") from exc
        return make_picture(0, data, type=3, desc="Cover", source="file")

    def _album_cover(self) -> None:
        """Store or clear the album art inside the app; audio files are never touched."""
        library = self.context.library
        payload = self._read_json()
        album = str(payload.get("album") or "").strip()
        artist = str(payload.get("album_artist") or payload.get("artist") or "").strip()
        if not album:
            self._error(400, "album required")
            return
        action = str(payload.get("action") or "set")
        if action not in {"set", "remove"}:
            self._error(400, "unsupported action")
            return

        picture = None
        if action == "set":
            try:
                picture = self._cover_picture(str(payload.get("cover") or ""))
            except ValueError as exc:
                status = 413 if str(exc) == "cover too large" else 400
                self._error(status, str(exc))
                return

        if not library.album_tracks(album, artist):
            self._error(404, "no tracks in album")
            return

        if action == "remove":
            library.remove_album_cover(album)
            self._json({"custom": False})
            return

        digest = self.context.thumbs.store(picture.data)
        library.set_album_cover(album, digest)
        self._json({"custom": True, "cover_hash": digest})

    def _backup_files(self) -> list[Path]:
        """Every `.bak` under the library roots, counted once."""
        seen: set[str] = set()
        files: list[Path] = []
        for folder in self.context.library.folders():
            root = Path(folder["path"])
            if not root.is_dir():
                continue
            try:
                candidates = root.rglob("*.bak")
                for item in candidates:
                    key = str(item).lower()
                    if key in seen or not item.is_file():
                        continue
                    seen.add(key)
                    files.append(item)
            except OSError:
                continue
        return files

    def _update_apply(self) -> None:
        """Download the newest release and swap the install after the app exits."""
        import shutil
        import sys
        import zipfile

        from .. import __version__

        if not getattr(sys, "frozen", False):
            self._error(400, "обновление доступно только в собранном приложении")
            return
        try:
            release = latest_release()
        except Exception as exc:
            self._error(502, f"не удалось проверить обновления: {exc}")
            return
        tag = str(release.get("tag_name") or "").lstrip("vV")
        if version_tuple(tag) <= version_tuple(__version__):
            self._error(409, "обновление не требуется")
            return
        asset = next(
            (
                item
                for item in release.get("assets", [])
                if str(item.get("name", "")).lower().endswith(".zip")
            ),
            None,
        )
        url = str((asset or {}).get("browser_download_url") or "")
        if not url.startswith(f"https://github.com/{UPDATE_REPO}/"):
            self._error(400, "в релизе нет подходящего архива")
            return

        update_dir = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Choreia" / "update"
        if update_dir.exists():
            shutil.rmtree(update_dir, ignore_errors=True)
        update_dir.mkdir(parents=True, exist_ok=True)
        archive = update_dir / "update.zip"
        try:
            request = urlrequest.Request(url, headers={"User-Agent": "Choreia/1.0"})
            with urlrequest.urlopen(request, timeout=180) as response, archive.open("wb") as handle:
                shutil.copyfileobj(response, handle)
            root = (update_dir / "new").resolve()
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.infolist():
                    target = (root / member.filename).resolve()
                    if not str(target).startswith(str(root)):
                        raise RuntimeError("архив содержит недопустимый путь")
                bundle.extractall(root)
        except Exception as exc:
            self._error(500, f"не удалось скачать обновление: {exc}")
            return

        executable = next(update_dir.rglob("Choreia.exe"), None)
        if executable is None:
            self._error(500, "в архиве нет Choreia.exe")
            return
        install_dir = Path(sys.executable).parent
        script = update_dir / "apply.ps1"
        script.write_text(
            'Start-Sleep -Seconds 3\n'
            f'robocopy "{executable.parent}" "{install_dir}" /MIR /NFL /NDL /NJH /NJS /R:2 /W:1\n'
            f'Start-Process "{install_dir / "Choreia.exe"}"\n',
            encoding="utf-8-sig",
        )
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.Popen(
                [
                    "cmd",
                    "/c",
                    "start",
                    "",
                    "/min",
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-WindowStyle",
                    "Hidden",
                    "-File",
                    str(script),
                ],
                creationflags=flags,
                close_fds=True,
            )
        except OSError as exc:
            self._error(500, f"не удалось запустить обновление: {exc}")
            return
        self._json({"ok": True, "version": tag})
        threading.Timer(2.0, lambda: os._exit(0)).start()

    def _online_download(self) -> None:
        from pathlib import Path

        from ..sources import hitmos

        library = self.context.library
        payload = self._read_json()
        song_id = str(payload.get("id") or "").strip()
        folder_raw = str(payload.get("folder") or "").strip()
        title = str(payload.get("title") or "").strip()
        artist = str(payload.get("artist") or "").strip()
        cover_url = str(payload.get("cover") or "").strip()
        if not song_id or not folder_raw:
            self._error(400, "id and folder are required")
            return

        folder = Path(folder_raw)
        key = os.path.normpath(str(folder)).lower()
        roots = [os.path.normpath(item["path"]).lower() for item in library.folders()]
        inside = any(key == root or key.startswith(root + "\\") for root in roots)
        if not folder.is_dir():
            self._error(400, "folder not found")
            return

        job = secrets.token_urlsafe(6)
        state = {
            "status": "resolving",
            "received": 0,
            "total": 0,
            "path": "",
            "error": "",
            "title": title,
            "artist": artist,
            "indexed": False,
        }
        with self.context.online_lock:
            if len(self.context.online_jobs) > 50:
                self.context.online_jobs.clear()
            self.context.online_jobs[job] = state

        def progress(received: int, total: int) -> None:
            with self.context.online_lock:
                state["received"] = received
                if total:
                    state["total"] = total
                state["status"] = "downloading"

        def work() -> None:
            temporary = None
            try:
                info = hitmos.resolve(song_id)
                target = hitmos.unique_path(folder, hitmos.safe_filename(artist, title))
                temporary = target.with_name(target.name + ".part")
                hitmos.download(info["download"], temporary, progress)
                os.replace(temporary, target)
                if cover_url:
                    try:
                        picture = make_picture(
                            0, hitmos.fetch_image(cover_url), type=3, desc="Cover", source="hitmos"
                        )
                        report = inspect_file(target)
                        clean_file(target, keep=picture, metadata=report.fields, backup=False)
                    except Exception:
                        pass
                if inside:
                    refresh_track(library, self.context.thumbs, target)
                with self.context.online_lock:
                    state["status"] = "done"
                    state["path"] = str(target)
                    state["indexed"] = inside
            except Exception as exc:
                if temporary is not None:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        pass
                with self.context.online_lock:
                    state["status"] = "error"
                    state["error"] = str(exc)

        threading.Thread(target=work, name="choreia-download", daemon=True).start()
        self._json({"job": job})

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
            try:
                keep = self._cover_picture(str(payload.get("cover") or ""))
            except ValueError as exc:
                status = 413 if str(exc) == "cover too large" else 400
                self._error(status, str(exc))
                return

        try:
            clean_file(source, keep=keep, metadata=metadata)
            updated = refresh_track(library, self.context.thumbs, source)
            library.clear_lyrics_miss(track_id)
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
        payload = self._read_json()
        force = bool(payload.get("force"))
        if not force and library.lyrics_miss(track_id):
            self._error(404, "lyrics not found")
            return
        found = lookup(
            str(track["artist"] or ""),
            str(track["title"] or ""),
            str(track["album"] or ""),
            float(track["duration"] or 0),
        )
        if not found:
            library.mark_lyrics_miss(track_id)
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
            source=str(found.get("source") or "lrclib"),
            instrumental=bool(found.get("instrumental")),
        )
        library.clear_lyrics_miss(track_id)
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
            tracks = library.album_tracks(album, artist)
            override = library.album_cover(album)
            cover_hash = override or next(
                (track["cover_hash"] for track in tracks if track["cover_hash"]), ""
            )
            self._json(
                {
                    "tracks": tracks,
                    "cover_hash": cover_hash,
                    "custom_cover": bool(override),
                }
            )
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
        if route == "online/search":
            from ..sources import hitmos

            text = (query.get("q") or [""])[0].strip()
            if not text:
                self._json({"results": []})
                return
            try:
                found = hitmos.search(text)
            except Exception as exc:
                self._error(502, f"поиск недоступен: {exc}")
                return
            self._json({"results": found})
            return
        if route == "online/progress":
            job_id = (query.get("id") or [""])[0]
            with self.context.online_lock:
                state = self.context.online_jobs.get(job_id)
                snapshot = dict(state) if state else None
            if snapshot is None:
                self._error(404, "no job")
                return
            self._json({"job": snapshot})
            return
        if route == "duplicates":
            self._json({"groups": library.duplicate_groups()})
            return
        if route == "backups":
            files = self._backup_files()
            total = 0
            for item in files:
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
            self._json({"count": len(files), "bytes": total})
            return
        if route == "update/check":
            from .. import __version__

            try:
                release = latest_release()
            except Exception as exc:
                self._error(502, f"не удалось проверить обновления: {exc}")
                return
            tag = str(release.get("tag_name") or "").lstrip("vV")
            asset = next(
                (
                    item
                    for item in release.get("assets", [])
                    if str(item.get("name", "")).lower().endswith(".zip")
                ),
                None,
            )
            self._json(
                {
                    "current": __version__,
                    "latest": tag,
                    "available": version_tuple(tag) > version_tuple(__version__),
                    "url": release.get("html_url") or "",
                    "notes": str(release.get("body") or "")[:1500],
                    "asset": asset.get("browser_download_url") if asset else "",
                }
            )
            return
        if route == "diagnostics":
            from .. import __version__

            root = self.context.thumbs.root
            rendered = [path for path in root.glob("*-*.jpg") if path.is_file()]
            cache_bytes = 0
            for path in rendered:
                try:
                    cache_bytes += path.stat().st_size
                except OSError:
                    continue
            self._json(
                {
                    "version": __version__,
                    "data_dir": str(root.parent.parent),
                    "cache_bytes": cache_bytes,
                    "genius_configured": bool(library.setting("genius_token")),
                    "genius_state": self.context.genius_state(),
                    "lyrics_cached": library.count_lyrics(),
                    "lyrics_bytes": library.lyrics_bytes(),
                }
            )
            return
        if route == "preferences":
            self._json({"preferences": library.settings_with_prefix("ui.")})
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
        try:
            size = int((query.get("size") or ["320"])[0])
        except ValueError:
            size = 320
        size = max(32, min(1024, size))
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
