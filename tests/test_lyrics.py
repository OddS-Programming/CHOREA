from __future__ import annotations

import pytest

from choreia.sources import lyrics


def test_lookup_prefers_matching_duration(monkeypatch) -> None:
    def fake_get(url: str):
        if "/get?" in url:
            raise RuntimeError("404")
        return [
            {"trackName": "Song", "artistName": "Artist", "duration": 200,
             "syncedLyrics": "[00:01.00] wrong", "plainLyrics": "wrong"},
            {"trackName": "Song", "artistName": "Artist", "duration": 100,
             "syncedLyrics": "[00:02.00] right", "plainLyrics": "right"},
        ]

    monkeypatch.setattr(lyrics, "_get", fake_get)
    result = lyrics.lookup("Artist", "Song", "", 100)

    assert result is not None
    assert result["synced"] == "[00:02.00] right"


def test_lookup_derives_plain_from_synced(monkeypatch) -> None:
    def fake_get(url: str):
        return {
            "trackName": "Song",
            "artistName": "Artist",
            "duration": 100,
            "syncedLyrics": "[00:01.00] one\n[00:02.00] two",
            "plainLyrics": "",
        }

    monkeypatch.setattr(lyrics, "_get", fake_get)
    result = lyrics.lookup("Artist", "Song", "", 100)

    assert result["plain"] == "one\ntwo"
    assert result["source"] == "lrclib"


def test_lookup_returns_none_when_offline(monkeypatch) -> None:
    def failing(url: str):
        raise RuntimeError("network down")

    monkeypatch.setattr(lyrics, "_get", failing)
    assert lyrics.lookup("Artist", "Song") is None


def test_lookup_rejects_instrumental(monkeypatch) -> None:
    def fake_get(url: str):
        if "/get?" in url:
            return {"instrumental": True, "plainLyrics": "", "syncedLyrics": ""}
        return []

    monkeypatch.setattr(lyrics, "_get", fake_get)
    assert lyrics.lookup("Artist", "Song") is None
