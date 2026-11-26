"""Synced lyrics from LRCLIB: free, no key, LRC timestamps."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

API = "https://lrclib.net/api"
USER_AGENT = "Choreia/1.0 (https://github.com/OddS-Programming/CHOREA)"


def _get(url: str):
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def _normalize(item: dict) -> dict | None:
    synced = item.get("syncedLyrics") or ""
    plain = item.get("plainLyrics") or ""
    if not synced.strip() and not plain.strip():
        return None
    if not plain.strip() and synced.strip():
        plain = "\n".join(
            line.split("]", 1)[1].strip() if line.startswith("[") and "]" in line else line
            for line in synced.splitlines()
        )
    return {
        "source": "lrclib",
        "plain": plain.strip(),
        "synced": synced.strip() or None,
        "instrumental": bool(item.get("instrumental")),
    }


def _score(item: dict, artist: str, title: str, duration: float) -> int:
    score = 0
    if str(item.get("trackName", "")).strip().lower() == title.strip().lower():
        score += 2
    if str(item.get("artistName", "")).strip().lower() == artist.strip().lower():
        score += 2
    item_duration = item.get("duration") or 0
    if duration and item_duration and abs(float(item_duration) - float(duration)) <= 3:
        score += 3
    return score


def lookup(artist: str, title: str, album: str = "", duration: float = 0) -> dict | None:
    """Find lyrics by exact match first, then by search with duration scoring."""
    if not artist.strip() or not title.strip():
        return None

    params = {"artist_name": artist, "track_name": title}
    if album.strip():
        params["album_name"] = album
    if duration:
        params["duration"] = str(int(round(float(duration))))
    try:
        found = _get(f"{API}/get?{urllib.parse.urlencode(params)}")
        if isinstance(found, dict) and not found.get("instrumental"):
            normalized = _normalize(found)
            if normalized:
                return normalized
    except Exception:
        pass

    query = f"{artist} {title}".strip()
    try:
        results = _get(f"{API}/search?{urllib.parse.urlencode({'q': query})}")
    except Exception:
        return None
    if not isinstance(results, list):
        return None

    best: tuple[int, dict] | None = None
    for item in results[:15]:
        if not isinstance(item, dict) or item.get("instrumental"):
            continue
        if not (item.get("syncedLyrics") or item.get("plainLyrics")):
            continue
        score = _score(item, artist, title, duration)
        if best is None or score > best[0]:
            best = (score, item)

    if best is None:
        return None
    return _normalize(best[1])
