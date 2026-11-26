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


def _post(server, path: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.port}{path}",
        data=data,
        headers={"Content-Type": "application/json", "X-Token": server.context.token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


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


def test_folder_can_be_added_and_removed(server, tmp_path) -> None:
    running, _library, _track = server
    status, payload = _post(running, "/api/folders", {"path": str(tmp_path / "Album")})
    assert status == 200
    folder_id = payload["id"]

    request = urllib.request.Request(
        f"http://127.0.0.1:{running.port}/api/folders/{folder_id}",
        headers={"X-Token": running.context.token},
        method="DELETE",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        assert response.status == 200

    status, _headers, body = _get(running, "/api/folders", {"X-Token": running.context.token})
    assert status == 200
    assert json.loads(body)["folders"] == []


def test_lyrics_are_saved_and_read(server) -> None:
    running, _library, _track = server
    status, payload = _post(
        running,
        "/api/lyrics/1",
        {"text": "[00:01.00] Первая строка\n[00:05.50] Вторая строка"},
    )
    assert status == 200
    assert payload["lyrics"]["synced"].startswith("[00:01.00]")
    assert payload["lyrics"]["plain"].splitlines() == ["Первая строка", "Вторая строка"]

    status, _headers, body = _get(running, "/api/lyrics/1", {"X-Token": running.context.token})
    assert status == 200
    assert json.loads(body)["lyrics"]["plain"].splitlines()[0] == "Первая строка"


def test_plain_lyrics_have_no_synced_block(server) -> None:
    running, _library, _track = server
    status, payload = _post(running, "/api/lyrics/1", {"text": "Просто текст без таймкодов"})
    assert status == 200
    assert payload["lyrics"]["synced"] is None
    assert payload["lyrics"]["plain"] == "Просто текст без таймкодов"


def test_lyrics_can_be_deleted(server) -> None:
    running, _library, _track = server
    _post(running, "/api/lyrics/1", {"text": "строка"})
    status, payload = _post(running, "/api/lyrics/1", {"text": ""})
    assert status == 200 and payload["deleted"] is True
    status, _headers, body = _get(running, "/api/lyrics/1", {"X-Token": running.context.token})
    assert status == 200
    assert json.loads(body)["lyrics"] is None


def test_cover_can_be_set_and_removed(server) -> None:
    import base64
    import io

    from PIL import Image

    from choreia.core import inspect_file

    running, _library, track = server
    buffer = io.BytesIO()
    Image.new("RGB", (1200, 1200), (200, 30, 30)).save(buffer, "JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    status, payload = _post(
        running,
        "/api/tracks/1",
        {"title": "Cover test", "cover_action": "set", "cover": f"data:image/jpeg;base64,{encoded}"},
    )
    assert status == 200
    assert payload["track"]["cover_hash"]
    report = inspect_file(track)
    assert len(report.pictures) == 1
    assert report.pictures[0].width == 1200

    status, _payload = _post(running, "/api/tracks/1", {"title": "No art", "cover_action": "remove"})
    assert status == 200
    assert inspect_file(track).pictures == []


def test_bad_cover_is_rejected(server) -> None:
    running, _library, _track = server
    status, _payload = _post(
        running,
        "/api/tracks/1",
        {"title": "x", "cover_action": "set", "cover": "data:image/jpeg;base64,bm90IGFuIGltYWdl"},
    )
    assert status == 400


def test_cover_can_apply_to_whole_album(server) -> None:
    import base64
    import io
    import shutil

    from PIL import Image

    from choreia.core import inspect_file

    running, library, track = server
    second = track.parent / "second.mp3"
    shutil.copy2(track, second)
    library.upsert_track(path=str(second), title="Second", album="Album X", album_artist="Artist")
    library.upsert_track(path=str(track), title="First", album="Album X", album_artist="Artist")

    buffer = io.BytesIO()
    Image.new("RGB", (1000, 1000), (10, 120, 10)).save(buffer, "JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    status, payload = _post(
        running,
        "/api/tracks/1",
        {
            "title": "First",
            "album": "Album X",
            "album_artist": "Artist",
            "cover_action": "set",
            "cover": f"data:image/jpeg;base64,{encoded}",
            "apply_to_album": True,
        },
    )

    assert status == 200
    assert payload["album_updated"] == 1
    assert len(inspect_file(track).pictures) == 1
    assert len(inspect_file(second).pictures) == 1


def test_reveal_missing_path(server, tmp_path) -> None:
    running, _library, _track = server
    status, _payload = _post(running, "/api/reveal", {"path": str(tmp_path / "missing")})
    assert status == 404


def test_playlist_api(server) -> None:
    running, _library, _track = server
    status, payload = _post(running, "/api/playlists", {"name": "Mix"})
    assert status == 200
    playlist_id = payload["id"]

    status, _payload = _post(running, f"/api/playlists/{playlist_id}/tracks", {"track_id": 1})
    assert status == 200

    status, _headers, body = _get(
        running, f"/api/playlists/{playlist_id}", {"X-Token": running.context.token}
    )
    assert status == 200
    data = json.loads(body)
    assert data["playlist"]["name"] == "Mix"
    assert [track["id"] for track in data["tracks"]] == [1]

    assert _post(running, "/api/playlists", {"name": "Mix"})[0] == 409


def test_add_files_indexes_tracks(server, tmp_path) -> None:
    import helpers

    running, library, _track = server
    extra = helpers.copy_asset("mp3", tmp_path / "extra.mp3")

    status, payload = _post(running, "/api/add-files", {"paths": [str(extra), "C:/nope.mp3"]})

    assert status == 200
    assert payload["added"] == 1
    assert library.track_by_path(str(extra)) is not None


def test_update_track_metadata(server) -> None:
    from choreia.core import inspect_file

    running, _library, track = server
    status, payload = _post(
        running,
        "/api/tracks/1",
        {"title": "Новое имя", "artist": "Ёж", "album": "Альбом"},
    )

    assert status == 200
    assert payload["track"]["title"] == "Новое имя"
    assert payload["track"]["artist"] == "Ёж"
    written = inspect_file(track)
    assert written.fields["title"] == "Новое имя"
    assert written.fields["artist"] == "Ёж"


def test_update_unknown_track(server) -> None:
    running, _library, _track = server
    status, _payload = _post(running, "/api/tracks/999", {"title": "x"})
    assert status == 404


def test_unknown_track_is_404(server) -> None:
    running, _library, _track = server
    assert _get(running, f"/media/999?t={running.context.token}")[0] == 404
