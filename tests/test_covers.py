from __future__ import annotations

import io
import json

from PIL import Image

from choreia.sources import covers


def _jpeg(size: tuple[int, int] = (600, 600), color=(120, 80, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "JPEG")
    return buffer.getvalue()


def test_search_merges_sources_and_builds_data_urls(monkeypatch) -> None:
    image = _jpeg()

    def fake_get(url: str, headers=None):
        if "itunes" in url:
            return json.dumps(
                {
                    "results": [
                        {
                            "collectionName": "Album",
                            "artistName": "Artist",
                            "artworkUrl100": "https://img/100x100bb.jpg",
                        }
                    ]
                }
            ).encode()
        if "deezer" in url:
            return json.dumps(
                {"data": [{"title": "Album", "cover_xl": "https://dz/cover.jpg"}]}
            ).encode()
        if "musicbrainz" in url:
            return json.dumps({"release-groups": [{"id": "abc", "title": "Album"}]}).encode()
        if "genius" in url:
            return json.dumps(
                {"response": {"hits": [{"result": {"title": "Track", "song_art_image_url": "https://gen/art.jpg"}}]}}
            ).encode()
        return image

    monkeypatch.setattr(covers, "_get", fake_get)

    found = covers.search("Artist", "Album", "Track", genius_token="secret")

    urls = [item["thumb"] for item in found]
    assert len(found) == 4
    assert all(url.startswith("data:image/jpeg;base64,") for url in urls)
    assert [item["source"] for item in found] == [
        "iTunes",
        "Cover Art Archive",
        "Deezer",
        "Genius",
    ]


def test_search_survives_a_broken_source(monkeypatch) -> None:
    image = _jpeg()

    def fake_get(url: str, headers=None):
        if "itunes" in url:
            raise RuntimeError("network down")
        if "deezer" in url:
            return json.dumps({"data": [{"title": "Album", "cover_xl": "https://dz/a.jpg"}]}).encode()
        if url.startswith("https://dz/"):
            return image
        return b"[]"

    monkeypatch.setattr(covers, "_get", fake_get)

    found = covers.search("Artist", "Album", "Track")

    assert [item["source"] for item in found] == ["Deezer"]


def test_search_skips_genius_without_token(monkeypatch) -> None:
    calls: list[str] = []

    def fake_get(url: str, headers=None):
        calls.append(url)
        return json.dumps({"results": []}).encode()

    monkeypatch.setattr(covers, "_get", fake_get)

    covers.search("Artist", "Album", "Track")

    assert not any("genius" in url for url in calls)


def test_search_ignores_non_image_payloads(monkeypatch) -> None:
    def fake_get(url: str, headers=None):
        if "itunes" in url:
            return json.dumps(
                {
                    "results": [
                        {
                            "collectionName": "Album",
                            "artistName": "Artist",
                            "artworkUrl100": "https://img/100x100bb.jpg",
                        }
                    ]
                }
            ).encode()
        return b"<html>not an image</html>"

    monkeypatch.setattr(covers, "_get", fake_get)

    assert covers.search("Artist", "Album", "Track") == []


def test_search_drops_unrelated_candidates(monkeypatch) -> None:
    def fake_get(url: str, headers=None):
        if "itunes" in url:
            return json.dumps(
                {
                    "results": [
                        {
                            "collectionName": "Honey - Single",
                            "artistName": "boy pablo",
                            "artworkUrl100": "https://img/100x100bb.jpg",
                        }
                    ]
                }
            ).encode()
        if url.startswith("https://img/"):
            return _jpeg()
        raise RuntimeError("nothing else")

    monkeypatch.setattr(covers, "_get", fake_get)

    assert covers.search("Radiohead", "Pablo Honey", "Creep") == []


def test_check_token_accepts_a_valid_token(monkeypatch) -> None:
    monkeypatch.setattr(covers, "_get_json", lambda url, headers=None: {"response": {}})

    assert covers.check_token("token") is True


def test_check_token_rejects_401(monkeypatch) -> None:
    import urllib.error

    def denied(url, headers=None):
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(covers, "_get_json", denied)

    assert covers.check_token("token") is False


def test_check_token_requires_a_value() -> None:
    assert covers.check_token("   ") is False


def test_genius_prefers_the_album_cover(monkeypatch) -> None:
    def fake_json(url: str, headers=None):
        if "/search?" in url:
            return {
                "response": {
                    "hits": [
                        {
                            "result": {
                                "id": 1,
                                "title": "Creep",
                                "song_art_image_url": "https://gen/song.jpg",
                                "primary_artist": {"name": "Radiohead"},
                            }
                        },
                        {
                            "result": {
                                "id": 2,
                                "title": "Creep (Acoustic)",
                                "song_art_image_url": "https://gen/song2.jpg",
                                "primary_artist": {"name": "Radiohead"},
                            }
                        },
                    ]
                }
            }
        if "/songs/1" in url:
            return {
                "response": {
                    "song": {
                        "album": {"name": "Pablo Honey", "cover_art_url": "https://gen/album.jpg"}
                    }
                }
            }
        return {"response": {}}

    monkeypatch.setattr(covers, "_get_json", fake_json)

    found = covers._genius("Radiohead", "Pablo Honey", "Creep", "token")

    assert found[0]["url"] == "https://gen/album.jpg"
    assert found[0]["label"] == "Pablo Honey"
    assert found[1]["url"] == "https://gen/song2.jpg"


def test_genius_ignores_a_cover_of_another_album(monkeypatch) -> None:
    def fake_json(url: str, headers=None):
        if "/search?" in url:
            return {
                "response": {
                    "hits": [
                        {
                            "result": {
                                "id": 1,
                                "title": "Creep",
                                "song_art_image_url": "https://gen/song.jpg",
                                "primary_artist": {"name": "Radiohead"},
                            }
                        }
                    ]
                }
            }
        if "/songs/1" in url:
            return {
                "response": {
                    "song": {
                        "album": {"name": "Kid A", "cover_art_url": "https://gen/kida.jpg"}
                    }
                }
            }
        return {"response": {}}

    monkeypatch.setattr(covers, "_get_json", fake_json)

    found = covers._genius("Radiohead", "Pablo Honey", "Creep", "token")

    assert found[0]["url"] == "https://gen/song.jpg"


def test_itunes_falls_back_to_a_song_search(monkeypatch) -> None:
    calls = []

    def fake_json(url: str, headers=None):
        calls.append(url)
        if "entity=album" in url:
            return {"results": []}
        return {
            "results": [
                {
                    "trackName": "Creep",
                    "collectionName": "Pablo Honey",
                    "artistName": "Radiohead",
                    "artworkUrl100": "https://img/100x100bb.jpg",
                }
            ]
        }

    monkeypatch.setattr(covers, "_get_json", fake_json)

    found = covers._itunes("Radiohead", "Unknown Album", "Creep")

    assert found and found[0]["url"] == "https://img/1200x1200bb.jpg"
    assert any("entity=song" in url for url in calls)


def test_deezer_falls_back_to_a_track_search(monkeypatch) -> None:
    calls = []

    def fake_json(url: str, headers=None):
        calls.append(url)
        if "search/album" in url:
            return {"data": []}
        return {"data": [{"title": "Creep", "cover_xl": "https://dz/creep.jpg"}]}

    monkeypatch.setattr(covers, "_get_json", fake_json)

    found = covers._deezer("Radiohead", "Unknown Album", "Creep")

    assert found and found[0]["url"] == "https://dz/creep.jpg"
    assert any("api.deezer.com/search?" in url for url in calls)


def test_prepare_resizes_large_art(monkeypatch) -> None:
    monkeypatch.setattr(covers, "_get", lambda url, headers=None: _jpeg((3000, 3000)))

    prepared = covers._prepare("https://img/art.jpg")

    assert prepared is not None
    with Image.open(io.BytesIO(prepared["cover"])) as full:
        assert max(full.size) <= 1200
    with Image.open(io.BytesIO(prepared["thumb"])) as thumb:
        assert max(thumb.size) <= 220
