"""Search and download MP3 files from hitmos.fm, server-side.

The site renders its search page and song pages as HTML, so a light parser is
enough: search results carry ``/song/<id>`` links, and a song page embeds a
direct ``dwc*.hitmos.fm`` download URL.
"""

from __future__ import annotations

import html as html_lib
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

BASE = "https://rus.hitmos.fm"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)
TIMEOUT = 12
CHUNK = 256 * 1024

TITLE_RE = re.compile(
    r'<a class="[^"]*track-item__title[^"]*"[^>]*href="/song/(\d+)"[^>]*>(.*?)</a>', re.S
)
ARTIST_RE = re.compile(r'class="[^"]*track-item__artist[^"]*"[^>]*>([^<]*)<')
DURATION_RE = re.compile(r'class="[^"]*track-item__duration[^"]*">\s*([\d:]+)\s*<')
COVER_RE = re.compile(r'https://static[^"]*hitmos\.fm/[^"\s]+?\.(?:jpg|jpeg|webp|png)\?w=\d+')
DOWNLOAD_RE = re.compile(r'https://dwc\d*\.hitmos\.fm/[^"\\\s]+\.mp3')
PLAY_RE = re.compile(r'https://plc\d*\.hitmos\.fm/[^"\\\s]+\.mp3')

Progress = Callable[[int, int], None]


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "ru,en;q=0.8",
            "Referer": BASE + "/",
        },
    )


def _get_text(url: str) -> str:
    with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", "replace")


def search(query: str, limit: int = 20) -> list[dict]:
    """Return tracks found by the site search; an empty list when nothing matches."""
    query = " ".join((query or "").split())
    if not query:
        return []
    page = _get_text(f"{BASE}/search?" + urllib.parse.urlencode({"q": query}))
    matches = list(TITLE_RE.finditer(page))
    results: list[dict] = []
    seen: set[str] = set()
    for index, match in enumerate(matches):
        if len(results) >= limit:
            break
        song_id = match.group(1)
        if song_id in seen:
            continue
        seen.add(song_id)
        end = matches[index + 1].start() if index + 1 < len(matches) else match.start() + 2000
        tail = page[match.start():end]
        artist_match = ARTIST_RE.search(tail)
        duration_match = DURATION_RE.search(tail)
        covers = COVER_RE.findall(page[max(0, match.start() - 800):match.start() + 200])
        results.append(
            {
                "id": song_id,
                "title": html_lib.unescape(match.group(2)).strip(),
                "artist": html_lib.unescape(artist_match.group(1)).strip() if artist_match else "",
                "duration": duration_match.group(1) if duration_match else "",
                "cover": covers[-1] if covers else "",
            }
        )
    return results


def resolve(song_id: str) -> dict:
    """Return direct play and download URLs for one song page."""
    page = _get_text(f"{BASE}/song/{urllib.parse.quote(str(song_id))}")
    download = DOWNLOAD_RE.search(page)
    if download is None:
        raise RuntimeError("сайт не отдал ссылку на скачивание")
    play = PLAY_RE.search(page)
    return {"download": download.group(0), "play": play.group(0) if play else ""}


def download(url: str, target: Path, progress: Progress | None = None) -> int:
    """Stream one MP3 to `target`, reporting (received, total) to `progress`."""
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as response:
        total = int(response.headers.get("Content-Length") or 0)
        with target.open("wb") as handle:
            while True:
                block = response.read(CHUNK)
                if not block:
                    break
                handle.write(block)
                written += len(block)
                if progress is not None:
                    progress(written, total)
    return written


def fetch_image(url: str, limit: int = 12_000_000) -> bytes:
    """Download a cover image for a downloaded track."""
    with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as response:
        data = response.read(limit + 1)
    if not data or len(data) > limit:
        raise RuntimeError("обложка не получена")
    return data


def safe_filename(artist: str, title: str) -> str:
    raw = " - ".join(part for part in (artist.strip(), title.strip()) if part)
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", raw).strip(" .")
    return (cleaned or "track")[:140] + ".mp3"


def unique_path(folder: Path, filename: str) -> Path:
    target = folder / filename
    stem, suffix = target.stem, target.suffix
    counter = 1
    while target.exists():
        counter += 1
        target = folder / f"{stem} ({counter}){suffix}"
    return target
