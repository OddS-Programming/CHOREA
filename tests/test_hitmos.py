from __future__ import annotations

from pathlib import Path

from choreia.sources import hitmos

SEARCH_HTML = """
<div class="track-item">
  <img src="https://static-c1.hitmos.fm/i/one.webp?w=98"/>
  <a class="track-item__title track-item__link" href="/song/111">Creep</a>
  <a class="track-item__artist track-item__link" href="/artist/1">Radiohead</a>
  <span class="track-item__duration">03:57</span>
</div>
<div class="track-item">
  <img src="https://static-c1.hitmos.fm/i/two.webp?w=98"/>
  <a class="track-item__title track-item__link" href="/song/222">Creep &amp; Live</a>
  <span class="track-item__artist">Other Band</span>
  <span class="track-item__duration">04:10</span>
</div>
"""

SONG_HTML = """
<script>window.__DATA__ = {"play":"https://plc1.hitmos.fm/abc==.mp3",
"download":"https://dwc1.hitmos.fm/abc==.mp3"}</script>
"""


def test_search_parses_tracks(monkeypatch) -> None:
    monkeypatch.setattr(hitmos, "_get_text", lambda url: SEARCH_HTML)

    results = hitmos.search("creep")

    assert [item["id"] for item in results] == ["111", "222"]
    assert results[0]["title"] == "Creep"
    assert results[0]["artist"] == "Radiohead"
    assert results[0]["duration"] == "03:57"
    assert results[0]["cover"].endswith("one.webp?w=98")
    assert results[1]["title"] == "Creep & Live"
    assert results[1]["artist"] == "Other Band"


def test_search_ignores_an_empty_query(monkeypatch) -> None:
    called = {"count": 0}

    def get(url):
        called["count"] += 1
        return SEARCH_HTML

    monkeypatch.setattr(hitmos, "_get_text", get)

    assert hitmos.search("   ") == []
    assert called["count"] == 0


def test_resolve_finds_direct_urls(monkeypatch) -> None:
    monkeypatch.setattr(hitmos, "_get_text", lambda url: SONG_HTML)

    info = hitmos.resolve("222")

    assert info["download"] == "https://dwc1.hitmos.fm/abc==.mp3"
    assert info["play"] == "https://plc1.hitmos.fm/abc==.mp3"


def test_resolve_reports_a_missing_download_link(monkeypatch) -> None:
    monkeypatch.setattr(hitmos, "_get_text", lambda url: "<html></html>")

    try:
        hitmos.resolve("1")
    except RuntimeError:
        pass
    else:  # pragma: no cover - the parser must not invent a link
        raise AssertionError("expected RuntimeError")


def test_download_writes_chunks_and_reports_progress(monkeypatch, tmp_path: Path) -> None:
    class FakeResponse:
        headers = {"Content-Length": "8"}

        def __init__(self) -> None:
            self.chunks = [b"abcd", b"efgh", b""]

        def read(self, size: int) -> bytes:
            return self.chunks.pop(0)

        def __enter__(self):
            return self

        def __exit__(self, *args) -> bool:
            return False

    monkeypatch.setattr(hitmos.urllib.request, "urlopen", lambda request, timeout: FakeResponse())
    target = tmp_path / "track.mp3"
    seen: list[tuple[int, int]] = []

    written = hitmos.download("https://dwc1/x.mp3", target, lambda r, t: seen.append((r, t)))

    assert written == 8
    assert target.read_bytes() == b"abcdefgh"
    assert seen[-1] == (8, 8)


def test_safe_filename_strips_forbidden_characters() -> None:
    name = hitmos.safe_filename("AC/DC", 'Back: in "Black"')

    assert "/" not in name and ":" not in name and '"' not in name
    assert name.endswith(".mp3")
    assert name.startswith("AC DC - Back")


def test_unique_path_does_not_overwrite(tmp_path: Path) -> None:
    first = tmp_path / "Artist - Song.mp3"
    first.write_bytes(b"x")

    second = hitmos.unique_path(tmp_path, "Artist - Song.mp3")

    assert second.name == "Artist - Song (2).mp3"
    assert not second.exists()
