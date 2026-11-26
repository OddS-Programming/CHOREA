from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from choreia.library.db import Library
from choreia.library.thumbs import ThumbCache
from choreia.player.server import Server
import helpers


@pytest.fixture
def server(tmp_path: Path, asset):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html>choreia</html>", encoding="utf-8")
    library = Library(tmp_path / "library.db")
    thumbs = ThumbCache(tmp_path / "thumbs")
    folder = tmp_path / "Album"
    folder.mkdir()
    track = helpers.copy_asset("mp3", folder / "track.mp3")
    library.upsert_track(path=str(track), title="Track", artist="Artist", duration=1.0)

    running = Server(library, thumbs, web).start()
    try:
        yield running, library, track
    finally:
        running.stop()
        library.close()


def _get(server, path: str, headers: dict | None = None):
    request = urllib.request.Request(f"http://127.0.0.1:{server.port}{path}", headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def test_api_rejects_missing_token(server) -> None:
    running, _library, _track = server
    status, _headers, _body = _get(running, "/api/tracks")
    assert status == 403


def test_api_returns_tracks(server) -> None:
    running, _library, _track = server
    status, _headers, body = _get(running, "/api/tracks?sort=title", {"X-Token": running.context.token})
    assert status == 200
    payload = json.loads(body)
    assert payload["total"] == 1
    assert payload["tracks"][0]["title"] == "Track"


def test_index_requires_token(server) -> None:
    running, _library, _track = server
    assert _get(running, "/")[0] == 403
    status, _headers, body = _get(running, f"/?t={running.context.token}")
    assert status == 200
    assert b"choreia" in body


def test_range_request_returns_partial_content(server) -> None:
    running, _library, track = server
    size = track.stat().st_size
    status, headers, body = _get(
        running,
        f"/media/1?t={running.context.token}",
        {"Range": "bytes=0-1023"},
    )
    assert status == 206
    assert headers["Content-Range"] == f"bytes 0-1023/{size}"
    assert headers["Accept-Ranges"] == "bytes"
    assert len(body) == 1024


def test_full_media_request(server) -> None:
    running, _library, track = server
    status, headers, body = _get(running, f"/media/1?t={running.context.token}")
    assert status == 200
    assert len(body) == track.stat().st_size


def test_media_requires_token(server) -> None:
    running, _library, _track = server
    assert _get(running, "/media/1")[0] == 403


def test_static_traversal_is_blocked(server) -> None:
    running, _library, _track = server
    connection = http.client.HTTPConnection("127.0.0.1", running.port, timeout=5)
    connection.request("GET", "/static/../library.db")
    response = connection.getresponse()
    response.read()
    assert response.status in (403, 404)
    connection.close()


def test_unknown_track_is_404(server) -> None:
    running, _library, _track = server
    assert _get(running, f"/media/999?t={running.context.token}")[0] == 404
