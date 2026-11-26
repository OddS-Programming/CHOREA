"""Local HTTP server: UI, media with Range, thumbnails, JSON API."""

from __future__ import annotations

import json
import mimetypes
import re
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from ..library.db import Library
from ..library.scanner import Scanner
from ..library.thumbs import ThumbCache

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
            cache = "no-cache"
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
            self.context.library.remove_folder(int(match.group(1)))
            self._json({"ok": True})
            return
        self._error(404, "not found")

    # ----------------------------------------------------------------- parts
    def _api(self, route: str, query: dict[str, list[str]]) -> None:
        library = self.context.library
        if route == "tracks":
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
