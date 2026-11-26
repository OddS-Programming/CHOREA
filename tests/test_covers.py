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


def test_prepare_resizes_large_art(monkeypatch) -> None:
    monkeypatch.setattr(covers, "_get", lambda url, headers=None: _jpeg((3000, 3000)))

    prepared = covers._prepare("https://img/art.jpg")

    assert prepared is not None
    with Image.open(io.BytesIO(prepared["cover"])) as full:
        assert max(full.size) <= 1200
    with Image.open(io.BytesIO(prepared["thumb"])) as thumb:
        assert max(thumb.size) <= 220
