from __future__ import annotations

from pathlib import Path

from choreia.library.db import Library


def _library(tmp_path: Path) -> Library:
    return Library(tmp_path / "library.db")


def test_upsert_returns_id_and_updates_in_place(tmp_path: Path) -> None:
    library = _library(tmp_path)

    first = library.upsert_track(path="C:/music/a.mp3", title="Alpha", artist="X", duration=10)
    second = library.upsert_track(path="C:/music/a.mp3", title="Beta", artist="X", duration=10)

    assert first > 0
    assert second == first
    assert library.track(first)["title"] == "Beta"
    assert library.count_tracks() == 1
    library.close()


def test_sorting_and_search(tmp_path: Path) -> None:
    library = _library(tmp_path)
    library.upsert_track(path="C:/m/1.mp3", title="Zebra", artist="Beta", album="Two", duration=5)
    library.upsert_track(path="C:/m/2.mp3", title="Apple", artist="Alpha", album="One", duration=7)
    library.upsert_track(path="C:/m/3.mp3", title="Mango", artist="Alpha", album="One", duration=6)

    by_artist = [track["title"] for track in library.list_tracks(sort="artist")]
    assert by_artist[:2] == ["Apple", "Mango"]

    assert [track["title"] for track in library.list_tracks(query="mango")] == ["Mango"]
    assert library.count_tracks("Alpha") == 2
    assert len(library.list_tracks(limit=1, offset=1)) == 1
    library.close()


def test_settings_survive_reopen(tmp_path: Path) -> None:
    path = tmp_path / "library.db"
    library = Library(path)
    library.set_setting("download_dir", "C:/Music")
    library.close()

    reopened = Library(path)
    assert reopened.setting("download_dir") == "C:/Music"
    assert reopened.setting("missing", "fallback") == "fallback"
    reopened.close()


def test_folders_are_added_once(tmp_path: Path) -> None:
    library = _library(tmp_path)

    first = library.add_folder("C:/Music/Album")
    second = library.add_folder("C:/Music/Album")

    assert first == second
    assert len(library.folders()) == 1
    library.remove_folder(first)
    assert library.folders() == []
    library.close()


def test_lyrics_roundtrip(tmp_path: Path) -> None:
    library = _library(tmp_path)
    track_id = library.upsert_track(path="C:/m/1.mp3", title="One")

    assert library.lyrics(track_id) is None
    library.set_lyrics(track_id, plain="первая строка", synced="[00:01.00] первая строка")
    saved = library.lyrics(track_id)
    assert saved["plain"] == "первая строка"
    assert saved["synced"].startswith("[00:01.00]")
    assert saved["source"] == "manual"

    library.set_lyrics(track_id, plain="вторая")
    assert library.lyrics(track_id)["plain"] == "вторая"
    assert library.lyrics(track_id)["synced"] is None

    library.delete_lyrics(track_id)
    assert library.lyrics(track_id) is None
    library.close()


def test_playlists(tmp_path: Path) -> None:
    library = _library(tmp_path)
    first = library.upsert_track(path="C:/m/1.mp3", title="One")
    second = library.upsert_track(path="C:/m/2.mp3", title="Two")

    playlist_id = library.create_playlist("Mix")
    assert library.playlists()[0]["tracks"] == 0

    library.add_to_playlist(playlist_id, first)
    library.add_to_playlist(playlist_id, second)
    assert [track["title"] for track in library.playlist_tracks(playlist_id)] == ["One", "Two"]

    library.remove_from_playlist(playlist_id, 0)
    tracks = library.playlist_tracks(playlist_id)
    assert [track["title"] for track in tracks] == ["Two"]
    assert [track["position"] for track in tracks] == [0]

    library.delete_playlist(playlist_id)
    assert library.playlists() == []
    library.close()


def test_albums_group_tracks(tmp_path: Path, asset) -> None:
    library = _library(tmp_path)
    library.upsert_track(path="C:/m/1.mp3", title="One", album="Same", album_artist="Artist", cover_hash="abc")
    library.upsert_track(path="C:/m/2.mp3", title="Two", album="Same", album_artist="Artist", cover_hash="")
    library.upsert_track(path="C:/m/3.mp3", title="Three", album="Other", album_artist="Artist")

    albums = library.albums()

    assert [item["album"] for item in albums] == ["Other", "Same"]
    same = albums[1]
    assert same["tracks"] == 2
    assert same["cover_hash"] == "abc"
    assert [track["title"] for track in library.album_tracks("Same", "Artist")] == ["One", "Two"]
    library.close()


def test_album_artist_falls_back_to_solo_track(tmp_path: Path) -> None:
    library = _library(tmp_path)
    library.upsert_track(path="C:/m/1.mp3", title="Solo", album="Mix", artist="Main")
    library.upsert_track(path="C:/m/2.mp3", title="Duo", album="Mix", artist="Main feat. Guest")
    library.upsert_track(path="C:/m/3.mp3", title="Third", album="Mix", artist="Guest")

    album = library.albums()[0]

    assert album["album_artist"] == "Main"
    library.close()


def test_browse_signature_changes_only_with_content(tmp_path: Path) -> None:
    library = _library(tmp_path)
    folder = tmp_path / "Album"
    folder.mkdir()
    track = folder / "one.mp3"
    track.write_bytes(b"x")
    library.upsert_track(path=str(track), title="One", artist="A", album="Album", duration=10)

    first = library.browse(str(folder))
    assert first["signature"]
    assert library.browse(str(folder))["signature"] == first["signature"]

    (folder / "Extras").mkdir()
    assert library.browse(str(folder))["signature"] != first["signature"]

    second = library.browse(str(folder))
    library.upsert_track(path=str(track), title="Renamed", artist="A", album="Album", duration=10)
    assert library.browse(str(folder))["signature"] != second["signature"]
    library.close()


def test_prune_missing_drops_deleted_files(tmp_path: Path) -> None:
    library = _library(tmp_path)
    gone = tmp_path / "gone.mp3"
    gone.write_bytes(b"x")
    kept = tmp_path / "kept.mp3"
    kept.write_bytes(b"x")
    gone_id = library.upsert_track(path=str(gone), title="Gone")
    library.upsert_track(path=str(kept), title="Kept")

    gone.unlink()

    assert library.prune_missing() == 1
    assert library.track(gone_id) is None
    assert library.count_tracks() == 1
    library.close()


def test_delete_tracks_by_path(tmp_path: Path) -> None:
    library = _library(tmp_path)
    library.upsert_track(path="C:/m/1.mp3", title="One")
    library.upsert_track(path="C:/m/2.mp3", title="Two")

    removed = library.delete_tracks(["C:/m/1.mp3"])

    assert removed == 1
    assert library.count_tracks() == 1
    library.close()
