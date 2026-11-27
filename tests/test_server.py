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


def test_add_path_handles_file_and_folder(server, tmp_path) -> None:
    import helpers

    running, _library, _track = server
    extra = helpers.copy_asset("mp3", tmp_path / "extra.mp3")

    status, payload = _post(running, "/api/add-path", {"path": str(extra)})
    assert status == 200
    assert payload["kind"] == "file" and payload["added"] == 1

    status, payload = _post(running, "/api/add-path", {"path": str(tmp_path)})
    assert status == 200
    assert payload["kind"] == "folder"

    status, _payload = _post(running, "/api/add-path", {"path": str(tmp_path / "missing")})
    assert status == 404


def test_mkdir_creates_folder_inside_library(server, tmp_path) -> None:
    running, library, _track = server
    root = tmp_path / "Album"
    root.mkdir(exist_ok=True)
    library.add_folder(root)
    target = root / "Sub"

    status, payload = _post(running, "/api/mkdir", {"path": str(target)})
    assert status == 200
    assert target.is_dir()
    assert payload["path"] == str(target)

    assert _post(running, "/api/mkdir", {"path": str(target)})[0] == 409
    outside = tmp_path / "outside"
    outside.mkdir()
    assert _post(running, "/api/mkdir", {"path": str(outside / "x")})[0] == 403


def test_upload_writes_file_into_folder(server, tmp_path) -> None:
    import urllib.parse

    import helpers

    running, library, _track = server
    folder = tmp_path / "Uploads"
    folder.mkdir()
    library.add_folder(folder)
    data = (helpers.ASSETS / "tone.mp3").read_bytes()

    def upload(name: str) -> None:
        request = urllib.request.Request(
            f"http://127.0.0.1:{running.port}/api/upload?path={urllib.parse.quote(str(folder))}",
            data=data,
            method="POST",
            headers={
                "X-Token": running.context.token,
                "X-Filename": urllib.parse.quote(name),
                "Content-Type": "application/octet-stream",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 200

    upload("new track.mp3")
    assert (folder / "new track.mp3").exists()
    assert library.track_by_path(str(folder / "new track.mp3")) is not None

    upload("new track.mp3")
    assert (folder / "new track (2).mp3").exists()


def test_delete_tracks_moves_to_recycle(server, monkeypatch) -> None:
    import choreia.player.dialogs as dialogs

    running, library, track = server
    library.add_folder(track.parent)
    deleted = []
    monkeypatch.setattr(dialogs, "recycle", lambda path: deleted.append(path) or True)

    status, payload = _post(running, "/api/delete-tracks", {"ids": [1]})

    assert status == 200
    assert payload["removed"] == 1
    assert deleted and deleted[0] == track
    assert library.track(1) is None


def test_delete_refuses_tracks_outside_library(server, monkeypatch) -> None:
    import choreia.player.dialogs as dialogs

    running, library, _track = server
    monkeypatch.setattr(dialogs, "recycle", lambda path: True)

    status, payload = _post(running, "/api/delete-tracks", {"ids": [1]})

    assert status == 200
    assert payload["removed"] == 0
    assert library.track(1) is not None


def test_single_track_endpoint(server) -> None:
    running, _library, _track = server

    status, _headers, body = _get(running, "/api/tracks/1", {"X-Token": running.context.token})

    assert status == 200
    assert json.loads(body)["track"]["title"] == "Track"


def test_single_track_missing(server) -> None:
    running, _library, _track = server

    status, _headers, _body = _get(running, "/api/tracks/999", {"X-Token": running.context.token})

    assert status == 404


def test_cover_search_then_fetch(server, monkeypatch) -> None:
    from choreia.sources import covers

    running, _library, _track = server
    monkeypatch.setattr(
        covers,
        "search",
        lambda artist, album, title, token="", limit=10: [
            {
                "source": "iTunes",
                "label": album,
                "artist": artist,
                "thumb": "data:image/jpeg;base64,AAA",
                "cover": "data:image/jpeg;base64,BBB",
            }
        ],
    )

    status, _headers, body = _get(
        running,
        "/api/cover-search?artist=Artist&album=Album&title=Track",
        {"X-Token": running.context.token},
    )
    assert status == 200
    payload = json.loads(body)
    assert payload["results"][0]["source"] == "iTunes"
    assert payload["results"][0]["thumb"] == "data:image/jpeg;base64,AAA"

    key = payload["results"][0]["key"]
    status, _headers, body = _get(running, f"/api/cover/{key}", {"X-Token": running.context.token})
    assert status == 200
    assert json.loads(body)["cover"] == "data:image/jpeg;base64,BBB"


def test_cover_search_without_network_results(server, monkeypatch) -> None:
    from choreia.sources import covers

    running, _library, _track = server
    monkeypatch.setattr(covers, "search", lambda *args, **kwargs: [])

    status, _headers, body = _get(
        running,
        "/api/cover-search?artist=Artist&album=Album&title=Track",
        {"X-Token": running.context.token},
    )

    assert status == 200
    assert json.loads(body)["results"] == []


def test_unknown_cover_key_is_404(server) -> None:
    running, _library, _track = server

    status, _headers, _body = _get(running, "/api/cover/missing", {"X-Token": running.context.token})

    assert status == 404


def test_shared_open_allows_replacing_a_playing_file(server, tmp_path) -> None:
    import sys

    from choreia.atomic import write_with_backup
    from choreia.player.server import open_shared

    if sys.platform != "win32":
        pytest.skip("Windows file sharing semantics")

    running, _library, track = server

    with open_shared(track) as handle:
        assert handle.read()
        write_with_backup(track, lambda temp: temp.write_bytes(b"new"), backup=False)

    assert track.read_bytes() == b"new"
    assert running.context.library.track(1) is not None


def _album_with_two_tracks(server):
    import base64
    import io

    from PIL import Image

    import helpers
    from choreia.core import clean_file

    running, library, track = server
    second = helpers.copy_asset("mp3", track.parent / "second.mp3")
    shared = {"artist": "Artist", "album": "Album", "album_artist": "Artist"}
    clean_file(track, keep=None, metadata={**shared, "title": "One"})
    clean_file(second, keep=None, metadata={**shared, "title": "Two"})
    library.upsert_track(
        path=str(track), title="One", artist="Artist", album="Album", album_artist="Artist", duration=1.0
    )
    library.upsert_track(
        path=str(second), title="Two", artist="Artist", album="Album", album_artist="Artist", duration=1.0
    )
    buffer = io.BytesIO()
    Image.new("RGB", (300, 300), (90, 60, 160)).save(buffer, "JPEG")
    cover = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()
    return running, track, second, cover


def test_album_cover_is_stored_in_the_app_only(server) -> None:
    running, track, second, cover = _album_with_two_tracks(server)
    library = running.context.library
    files = (track, second)
    before = {path: path.read_bytes() for path in files}
    before_backups = {
        path: (
            path.with_name(path.name + ".bak").exists(),
            path.with_name(path.name + ".bak").stat().st_mtime_ns
            if path.with_name(path.name + ".bak").exists()
            else 0,
        )
        for path in files
    }

    status, payload = _post(
        running,
        "/api/album-cover",
        {"album": "Album", "album_artist": "Artist", "action": "set", "cover": cover},
    )

    assert status == 200
    assert payload["custom"] is True
    digest = payload["cover_hash"]
    for path in files:
        assert path.read_bytes() == before[path]
        backup = path.with_name(path.name + ".bak")
        after = (backup.exists(), backup.stat().st_mtime_ns if backup.exists() else 0)
        assert after == before_backups[path]
    assert library.album_cover("Album") == digest
    assert (running.context.thumbs.root / f"{digest}.src").exists()

    album = next(item for item in library.albums() if item["album"] == "Album")
    assert album["custom_cover"] is True
    assert album["cover_hash"] == digest

    status, payload = _post(
        running, "/api/album-cover", {"album": "Album", "album_artist": "Artist", "action": "remove"}
    )

    assert status == 200
    assert payload["custom"] is False
    assert library.album_cover("Album") is None
    album = next(item for item in library.albums() if item["album"] == "Album")
    assert album["custom_cover"] is False
    assert album["cover_hash"] == ""


def test_album_cover_rejects_bad_input(server) -> None:
    running, _library, _track = server

    status, payload = _post(running, "/api/album-cover", {"album": "", "action": "remove"})
    assert status == 400

    status, payload = _post(running, "/api/album-cover", {"album": "Missing", "action": "remove"})
    assert status == 404

    status, payload = _post(
        running,
        "/api/album-cover",
        {"album": "Album", "action": "set", "cover": "data:image/jpeg;base64,bm90IGFuIGltYWdl"},
    )
    assert status == 400


def test_removing_nested_folder_keeps_its_tracks(server, tmp_path) -> None:
    import time

    import helpers

    running, library, track = server
    music = track.parent.parent / "Music"
    nested = music / "ximora"
    nested.mkdir(parents=True)
    inner = helpers.copy_asset("mp3", nested / "inner.mp3")
    music_root = library.add_folder(music)
    nested_root = library.add_folder(nested)
    inner_id = library.upsert_track(path=str(inner), title="Inner", folder_id=nested_root)

    request = urllib.request.Request(
        f"http://127.0.0.1:{running.port}/api/folders/{nested_root}",
        method="DELETE",
        headers={"X-Token": running.context.token},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.loads(response.read())

    assert payload["removed"] == 0
    assert payload["rescanning"] is True
    assert library.track(inner_id) is not None
    assert library.track(inner_id)["folder_id"] == music_root

    for _ in range(60):
        status, _headers, body = _get(
            running, "/api/scan/status", {"X-Token": running.context.token}
        )
        if status == 200 and not json.loads(body)["running"]:
            break
        time.sleep(0.05)


def test_scan_recovers_from_a_dead_worker(server, tmp_path) -> None:
    import threading
    import time

    running, _library, _track = server
    context = running.context
    context.scan.running = True
    dead = threading.Thread(target=lambda: None)
    dead.start()
    dead.join()
    context._scan_thread = dead
    folder = tmp_path / "Empty"
    folder.mkdir()

    assert context.start_scan(folder) is True

    for _ in range(100):
        if not context.scan.snapshot()["running"]:
            break
        time.sleep(0.02)
    assert context.scan.snapshot()["running"] is False


def test_scan_reports_a_thread_that_cannot_start(server, tmp_path, monkeypatch) -> None:
    import threading

    running, _library, _track = server
    context = running.context
    folder = tmp_path / "Empty"
    folder.mkdir()

    def boom(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading.Thread, "start", boom)

    assert context.start_scan(folder) is False
    assert context.scan.snapshot()["running"] is False
    assert "thread" in (context.scan.snapshot()["error"] or "")


def test_diagnostics_reports_version_and_cache(server) -> None:
    running, _library, _track = server
    root = running.context.thumbs.root
    (root / "abc-320.jpg").write_bytes(b"x" * 2048)
    (root / "abc.src").write_bytes(b"y" * 4096)

    status, _headers, body = _get(running, "/api/diagnostics", {"X-Token": running.context.token})
    payload = json.loads(body)

    assert status == 200
    assert payload["version"]
    assert payload["cache_bytes"] == 2048
    assert payload["genius_configured"] is False
    assert payload["genius_state"] == "none"
    assert payload["lyrics_cached"] == 0
    assert payload["lyrics_bytes"] == 0
    assert Path(payload["data_dir"]) == root.parent.parent


def test_diagnostics_reports_the_genius_token_state(server, monkeypatch) -> None:
    from choreia.sources import covers

    running, library, _track = server
    monkeypatch.setattr(covers, "check_token", lambda token: token == "good")

    library.set_setting("genius_token", "bad")
    _status, _headers, body = _get(
        running, "/api/diagnostics", {"X-Token": running.context.token}
    )
    assert json.loads(body)["genius_state"] == "invalid"

    library.set_setting("genius_token", "good")
    running.context.genius_check = None
    _status, _headers, body = _get(
        running, "/api/diagnostics", {"X-Token": running.context.token}
    )
    assert json.loads(body)["genius_state"] == "ok"

    library.set_setting("genius_token", "")
    running.context.genius_check = None
    _status, _headers, body = _get(
        running, "/api/diagnostics", {"X-Token": running.context.token}
    )
    assert json.loads(body)["genius_state"] == "none"


def test_settings_reject_an_invalid_genius_token(server, monkeypatch) -> None:
    from choreia.sources import covers

    running, library, _track = server
    monkeypatch.setattr(covers, "check_token", lambda token: False)

    status, payload = _post(
        running, "/api/settings", {"key": "genius_token", "value": "bad-token"}
    )

    assert status == 400
    assert "401" in payload["error"]
    assert not library.setting("genius_token")


def test_settings_store_a_valid_genius_token(server, monkeypatch) -> None:
    from choreia.sources import covers

    running, library, _track = server
    monkeypatch.setattr(covers, "check_token", lambda token: True)

    status, _payload = _post(
        running, "/api/settings", {"key": "genius_token", "value": "good-token"}
    )

    assert status == 200
    assert library.setting("genius_token") == "good-token"


def test_clear_cache_keeps_original_covers(server) -> None:
    running, _library, _track = server
    root = running.context.thumbs.root
    (root / "abc-320.jpg").write_bytes(b"x" * 1024)
    (root / "abc-640.jpg").write_bytes(b"x" * 512)
    (root / "abc.src").write_bytes(b"original")

    request = urllib.request.Request(
        f"http://127.0.0.1:{running.port}/api/cache",
        method="DELETE",
        headers={"X-Token": running.context.token},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.loads(response.read())

    assert payload == {"removed": 2, "freed": 1536}
    assert (root / "abc.src").exists()


def test_preferences_expose_only_ui_settings(server) -> None:
    running, library, _track = server
    library.set_setting("ui.autoLyrics", "0")
    library.set_setting("genius_token", "secret")

    status, _headers, body = _get(running, "/api/preferences", {"X-Token": running.context.token})

    assert status == 200
    assert json.loads(body)["preferences"] == {"ui.autoLyrics": "0"}

    _post(running, "/api/settings", {"key": "ui.lyricsVisible", "value": "1"})
    _status, _headers, body = _get(running, "/api/preferences", {"X-Token": running.context.token})

    assert json.loads(body)["preferences"]["ui.lyricsVisible"] == "1"


def test_album_cover_works_without_album_artist_tag(server) -> None:
    import base64
    import io

    from PIL import Image

    import helpers
    from choreia.core import clean_file

    running, library, track = server
    second = helpers.copy_asset("mp3", track.parent / "second.mp3")
    shared = {"artist": "CODE10", "album": "DEMOVERSION"}
    clean_file(track, keep=None, metadata={**shared, "title": "One"})
    clean_file(second, keep=None, metadata={**shared, "title": "Two"})
    library.upsert_track(
        path=str(track), title="One", artist="CODE10", album="DEMOVERSION", duration=1.0
    )
    library.upsert_track(
        path=str(second), title="Two", artist="CODE10", album="DEMOVERSION", duration=1.0
    )
    buffer = io.BytesIO()
    Image.new("RGB", (300, 300), (40, 90, 160)).save(buffer, "JPEG")
    cover = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()

    status, payload = _post(
        running,
        "/api/album-cover",
        {"album": "DEMOVERSION", "album_artist": "CODE10", "action": "set", "cover": cover},
    )

    assert status == 200
    assert payload["custom"] is True
    assert library.album_cover("DEMOVERSION") == payload["cover_hash"]


def test_clear_all_lyrics(server) -> None:
    running, library, _track = server
    library.set_lyrics(1, plain="one line", source="manual")
    library.mark_lyrics_miss(1)

    request = urllib.request.Request(
        f"http://127.0.0.1:{running.port}/api/lyrics",
        method="DELETE",
        headers={"X-Token": running.context.token},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.loads(response.read())

    assert payload["removed"] == 1
    assert library.count_lyrics() == 0
    assert library.lyrics_miss(1) is False


def test_fetch_stores_the_provider_source(server, monkeypatch) -> None:
    from choreia.sources import lyrics as lyrics_source

    running, library, _track = server
    monkeypatch.setattr(
        lyrics_source,
        "lookup",
        lambda *args, **kwargs: {
            "source": "lyrics.ovh",
            "plain": "plain text",
            "synced": None,
            "instrumental": False,
        },
    )

    status, payload = _post(running, "/api/lyrics/1/fetch", {})

    assert status == 200
    assert library.lyrics(1)["source"] == "lyrics.ovh"


def test_fetch_caches_a_miss_until_forced(server, monkeypatch) -> None:
    from choreia.sources import lyrics as lyrics_source

    running, library, _track = server
    calls = {"count": 0}

    def missing(*args, **kwargs):
        calls["count"] += 1
        return None

    monkeypatch.setattr(lyrics_source, "lookup", missing)

    assert _post(running, "/api/lyrics/1/fetch", {})[0] == 404
    assert library.lyrics_miss(1) is True

    assert _post(running, "/api/lyrics/1/fetch", {})[0] == 404
    assert calls["count"] == 1

    assert _post(running, "/api/lyrics/1/fetch", {"force": True})[0] == 404
    assert calls["count"] == 2


def test_pick_folder_endpoint(server, monkeypatch) -> None:
    from choreia.player import dialogs

    running, _library, _track = server
    monkeypatch.setattr(dialogs, "pick_folder", lambda initial="": r"C:\Music")

    status, payload = _post(running, "/api/pick-folder", {"initial": "C:\\"})
    assert status == 200
    assert payload == {"path": "C:\\Music"}

    monkeypatch.setattr(dialogs, "pick_folder", lambda initial="": None)
    status, payload = _post(running, "/api/pick-folder", {})
    assert status == 200
    assert payload == {"cancelled": True}

    def boom(initial=""):
        raise RuntimeError("PowerShell недоступен")

    monkeypatch.setattr(dialogs, "pick_folder", boom)
    status, payload = _post(running, "/api/pick-folder", {})
    assert status == 500


def test_online_search_endpoint(server, monkeypatch) -> None:
    from choreia.sources import hitmos

    running, _library, _track = server
    monkeypatch.setattr(
        hitmos,
        "search",
        lambda query, limit=20: [{"id": "1", "title": query, "artist": "A", "duration": "1:00", "cover": ""}],
    )

    status, _headers, body = _get(
        running, "/api/online/search?q=creep", {"X-Token": running.context.token}
    )

    assert status == 200
    assert json.loads(body)["results"][0]["title"] == "creep"


def test_online_download_job_indexes_the_file(server, monkeypatch) -> None:
    import time

    import helpers
    from choreia.sources import hitmos

    running, library, track = server
    library.add_folder(track.parent)
    data = (helpers.ASSETS / "tone.mp3").read_bytes()

    monkeypatch.setattr(
        hitmos, "resolve", lambda song_id: {"download": "https://dwc1/x.mp3", "play": ""}
    )

    def fake_download(url, target, progress=None):
        target.write_bytes(data)
        if progress:
            progress(len(data), len(data))
        return len(data)

    monkeypatch.setattr(hitmos, "download", fake_download)

    status, payload = _post(
        running,
        "/api/online/download",
        {"id": "1", "folder": str(track.parent), "title": "New Track", "artist": "Artist"},
    )
    assert status == 200
    job_id = payload["job"]

    job = None
    for _ in range(100):
        _status, _headers, body = _get(
            running, f"/api/online/progress?id={job_id}", {"X-Token": running.context.token}
        )
        job = json.loads(body)["job"]
        if job["status"] in {"done", "error"}:
            break
        time.sleep(0.05)

    assert job is not None and job["status"] == "done"
    target = Path(job["path"])
    assert target.name == "Artist - New Track.mp3"
    assert target.exists()
    assert library.track_by_path(str(target)) is not None


def test_online_download_outside_the_library_is_not_indexed(server, tmp_path, monkeypatch) -> None:
    import time

    import helpers
    from choreia.sources import hitmos

    running, library, _track = server
    outside = tmp_path / "Outside"
    outside.mkdir()
    data = (helpers.ASSETS / "tone.mp3").read_bytes()
    monkeypatch.setattr(
        hitmos, "resolve", lambda song_id: {"download": "https://dwc1/x.mp3", "play": ""}
    )

    def fake_download(url, target, progress=None):
        target.write_bytes(data)
        return len(data)

    monkeypatch.setattr(hitmos, "download", fake_download)

    status, payload = _post(
        running,
        "/api/online/download",
        {"id": "1", "folder": str(outside), "title": "T", "artist": "A"},
    )
    assert status == 200
    job_id = payload["job"]

    job = None
    for _ in range(100):
        _status, _headers, body = _get(
            running, f"/api/online/progress?id={job_id}", {"X-Token": running.context.token}
        )
        job = json.loads(body)["job"]
        if job["status"] in {"done", "error"}:
            break
        time.sleep(0.05)

    assert job is not None and job["status"] == "done"
    assert job["indexed"] is False
    assert Path(job["path"]).exists()
    assert library.track_by_path(job["path"]) is None


def test_online_download_needs_an_existing_folder(server, tmp_path) -> None:
    running, _library, _track = server

    status, _payload = _post(
        running,
        "/api/online/download",
        {"id": "1", "folder": str(tmp_path / "Missing"), "title": "T", "artist": "A"},
    )

    assert status == 400


def test_backup_files_can_be_counted_and_removed(server) -> None:
    running, library, track = server
    root = track.parent
    library.add_folder(root)
    (root / "a.mp3.bak").write_bytes(b"x" * 100)
    (root / "b.mp3.bak").write_bytes(b"y" * 50)
    keep = root / "notes.txt"
    keep.write_bytes(b"z")

    _status, _headers, body = _get(running, "/api/backups", {"X-Token": running.context.token})
    assert json.loads(body) == {"count": 2, "bytes": 150}

    request = urllib.request.Request(
        f"http://127.0.0.1:{running.port}/api/backups",
        method="DELETE",
        headers={"X-Token": running.context.token},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.loads(response.read())

    assert payload == {"removed": 2, "freed": 150}
    assert not (root / "a.mp3.bak").exists()
    assert not (root / "b.mp3.bak").exists()
    assert keep.exists()


def test_duplicate_groups_endpoint(server) -> None:
    running, library, track = server
    library.upsert_track(path=str(track), title="Song", artist="A", duration=100)
    second = track.with_name("second.mp3")
    library.upsert_track(path=str(second), title="Song", artist="A", duration=101)

    status, _headers, body = _get(
        running, "/api/duplicates", {"X-Token": running.context.token}
    )

    assert status == 200
    groups = json.loads(body)["groups"]
    assert len(groups) == 1
    assert len(groups[0]["tracks"]) == 2


def test_thumb_requires_a_token(server) -> None:
    import helpers

    running, _library, _track = server
    digest, _path = running.context.thumbs.ensure(helpers.jpeg(), 320)

    assert _get(running, f"/thumb/{digest}?size=320")[0] == 403
    status, _headers, _body = _get(
        running, f"/thumb/{digest}?size=320", {"X-Token": running.context.token}
    )
    assert status == 200

    status, _headers, _body = _get(
        running, "/thumb/bad..digest?size=320", {"X-Token": running.context.token}
    )
    assert status == 400


def test_foreign_host_header_is_rejected(server) -> None:
    running, _library, _track = server
    connection = http.client.HTTPConnection("127.0.0.1", running.port, timeout=5)
    connection.request(
        "GET",
        "/api/folders",
        headers={"Host": "evil.example", "X-Token": running.context.token},
    )
    response = connection.getresponse()
    response.read()
    connection.close()

    assert response.status == 403


def test_move_a_playlist_track(server) -> None:
    running, library, track = server
    second = library.upsert_track(
        path=str(track.with_name("second.mp3")), title="Second", artist="Artist", duration=1.0
    )
    playlist = library.create_playlist("Order")
    library.add_to_playlist(playlist, 1)
    library.add_to_playlist(playlist, second)

    status, payload = _post(
        running, f"/api/playlists/{playlist}/move", {"from": 0, "to": 1}
    )

    assert status == 200
    assert payload["ok"] is True
    assert [item["id"] for item in library.playlist_tracks(playlist)] == [second, 1]


def test_version_tuple_orders_releases() -> None:
    from choreia.player.server import version_tuple

    assert version_tuple("v1.2.3") > version_tuple("1.2.2")
    assert version_tuple("1.10.0") > version_tuple("1.9.9")
    assert version_tuple("") == (0,)


def test_update_check_reports_a_newer_release(server, monkeypatch) -> None:
    from choreia.player import server as server_module

    running, _library, _track = server
    monkeypatch.setattr(
        server_module,
        "latest_release",
        lambda: {
            "tag_name": "v9.9.9",
            "html_url": "https://github.com/OddS-Programming/CHOREA/releases/tag/v9.9.9",
            "body": "notes",
            "assets": [
                {
                    "name": "Choreia-9.9.9-win64.zip",
                    "browser_download_url": "https://github.com/OddS-Programming/CHOREA/releases/download/v9.9.9/app.zip",
                }
            ],
        },
    )

    status, _headers, body = _get(
        running, "/api/update/check", {"X-Token": running.context.token}
    )
    payload = json.loads(body)

    assert status == 200
    assert payload["available"] is True
    assert payload["latest"] == "9.9.9"
    assert payload["asset"].endswith("app.zip")


def test_update_check_keeps_the_current_version(server, monkeypatch) -> None:
    from choreia.player import server as server_module

    running, _library, _track = server
    monkeypatch.setattr(
        server_module,
        "latest_release",
        lambda: {"tag_name": "v0.0.1", "html_url": "", "body": "", "assets": []},
    )

    _status, _headers, body = _get(
        running, "/api/update/check", {"X-Token": running.context.token}
    )

    assert json.loads(body)["available"] is False


def test_update_apply_requires_the_packaged_app(server) -> None:
    running, _library, _track = server

    status, _payload = _post(running, "/api/update/apply", {})

    assert status == 400


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
