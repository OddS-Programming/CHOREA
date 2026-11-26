"""Cover art from public catalogues: iTunes, Deezer, Cover Art Archive, Genius.

Only the user's explicit choice is ever applied: nothing is downloaded
automatically, so a cover the person set by hand always wins.
"""

from __future__ import annotations

import base64
import io
import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

USER_AGENT = "Choreia/1.0 ( https://github.com/OddS-Programming/CHOREA )"
TIMEOUT = 7
MAX_IMAGE_BYTES = 12_000_000
THUMB_SIZE = 220
COVER_SIZE = 1200


def _get(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, **({"Accept": "application/json"} if not headers else {}), **(headers or {})}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read(MAX_IMAGE_BYTES + 1)


def _get_json(url: str, headers: dict[str, str] | None = None):
    return json.loads(_get(url, headers).decode("utf-8"))


def _clean(value: str) -> str:
    return " ".join((value or "").split())


def _itunes_query(params: dict) -> list[dict]:
    data = _get_json("https://itunes.apple.com/search?" + urllib.parse.urlencode(params))
    found = []
    for item in data.get("results", []) if isinstance(data, dict) else []:
        artwork = item.get("artworkUrl100")
        if not artwork:
            continue
        big = artwork.replace("100x100bb", "1200x1200bb").replace("100x100", "1200x1200")
        found.append(
            {
                "source": "iTunes",
                "url": big,
                "label": item.get("collectionName") or item.get("trackName") or "",
                "artist": item.get("artistName") or "",
            }
        )
    return found


def _itunes(artist: str, album: str, title: str) -> list[dict]:
    term = _clean(" ".join(part for part in (artist, album) if part)) or _clean(title)
    if not term:
        return []
    if _clean(album):
        found = _itunes_query(
            {"term": term, "entity": "album", "attribute": "albumTerm", "limit": 8}
        )
        if found:
            return found
    return _itunes_query({"term": _clean(f"{artist} {title}") or term, "entity": "song", "limit": 8})


def _deezer_query(url: str) -> list[dict]:
    data = _get_json(url)
    items = data.get("data", []) if isinstance(data, dict) else []
    found = []
    for item in items:
        cover = item.get("cover_xl") or item.get("cover_big")
        album_data = item.get("album") if isinstance(item.get("album"), dict) else {}
        cover = cover or album_data.get("cover_xl") or album_data.get("cover_big")
        if not cover:
            continue
        found.append(
            {
                "source": "Deezer",
                "url": cover,
                "label": item.get("title") or album_data.get("title") or "",
                "artist": (item.get("artist") or {}).get("name", "")
                if isinstance(item.get("artist"), dict)
                else "",
            }
        )
    return found


def _deezer(artist: str, album: str, title: str) -> list[dict]:
    if _clean(album):
        query = f'artist:"{_clean(artist)}" album:"{_clean(album)}"'
        found = _deezer_query(
            "https://api.deezer.com/search/album?" + urllib.parse.urlencode({"q": query, "limit": 8})
        )
        if found:
            return found
    query = _clean(f"{artist} {title}")
    if not query.strip('" '):
        return []
    return _deezer_query(
        "https://api.deezer.com/search?" + urllib.parse.urlencode({"q": query, "limit": 8})
    )


def _cover_art_archive(artist: str, album: str, title: str) -> list[dict]:
    if not (_clean(artist) and _clean(album)):
        return []
    query = f'artist:"{_clean(artist)}" AND release:"{_clean(album)}"'
    data = _get_json(
        "https://musicbrainz.org/ws/2/release-group?"
        + urllib.parse.urlencode({"query": query, "fmt": "json", "limit": 4})
    )
    found = []
    for group in data.get("release-groups", []) if isinstance(data, dict) else []:
        mbid = group.get("id")
        if not mbid:
            continue
        found.append(
            {
                "source": "Cover Art Archive",
                "url": f"https://coverartarchive.org/release-group/{mbid}/front-1200",
                "label": group.get("title") or "",
                "artist": _clean(artist),
            }
        )
    return found


def _genius_album_art(song_id, token: str, album: str) -> tuple[str, str] | None:
    """Ask Genius for the album cover of a song; the search API has only song art."""
    if not song_id or not _clean(album):
        return None
    try:
        data = _get_json(
            f"https://api.genius.com/songs/{song_id}",
            {"Authorization": f"Bearer {token}"},
        )
    except Exception:
        return None
    song = (data.get("response") or {}).get("song") or {}
    album_data = song.get("album") or {}
    cover = album_data.get("cover_art_url")
    name = _clean(str(album_data.get("name") or ""))
    if not cover:
        return None
    requested = _norm(album)
    if requested and name and requested not in _norm(name) and _norm(name) not in requested:
        return None
    return cover, name or _clean(album)


def _genius(artist: str, album: str, title: str, token: str) -> list[dict]:
    if not token or not _clean(title):
        return []
    data = _get_json(
        "https://api.genius.com/search?" + urllib.parse.urlencode({"q": _clean(f"{artist} {title}")}),
        {"Authorization": f"Bearer {token}"},
    )
    hits = data.get("response", {}).get("hits", []) if isinstance(data, dict) else []
    hits = [hit for hit in hits if isinstance(hit, dict)][:6]
    album_cover = None
    if hits:
        album_cover = _genius_album_art(hits[0].get("result", {}).get("id"), token, album)

    found = []
    for index, hit in enumerate(hits):
        result = hit.get("result", {})
        artwork = result.get("song_art_image_url") or result.get("header_image_url")
        label = result.get("title") or ""
        if index == 0 and album_cover:
            artwork, label = album_cover
        if not artwork or "default" in artwork:
            continue
        found.append(
            {
                "source": "Genius",
                "url": artwork,
                "label": label,
                "artist": (result.get("primary_artist") or {}).get("name", ""),
            }
        )
    return found


def _collect(fetchers) -> list[dict]:
    """Run every enabled source in parallel; one failing source never blocks the rest."""
    found: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(fetchers)) as pool:
        futures = [pool.submit(fetcher) for fetcher in fetchers]
    for future in futures:
        try:
            found.extend(future.result())
        except Exception:
            continue

    seen: set[str] = set()
    unique: list[dict] = []
    for item in found:
        key = item["url"].split("?")[0].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _prepare(url: str) -> dict | None:
    """Download one image and build a small preview plus an embeddable JPEG."""
    from PIL import Image, UnidentifiedImageError

    try:
        raw = _get(url)
        if len(raw) > MAX_IMAGE_BYTES:
            return None
        with Image.open(io.BytesIO(raw)) as image:
            image = image.convert("RGB")
            full = image.copy()
            full.thumbnail((COVER_SIZE, COVER_SIZE), Image.LANCZOS)
            thumb = image.copy()
            thumb.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
            full_buffer = io.BytesIO()
            full.save(full_buffer, "JPEG", quality=92)
            thumb_buffer = io.BytesIO()
            thumb.save(thumb_buffer, "JPEG", quality=82)
        return {"cover": full_buffer.getvalue(), "thumb": thumb_buffer.getvalue()}
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _as_data_url(data: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def _norm(value: str) -> str:
    return "".join(character for character in (value or "").lower() if character.isalnum())


def _score(item: dict, artist: str, album: str, title: str) -> int:
    """Rank candidates so an exact album/artist match shows first."""
    label = _norm(item.get("label", ""))
    name = _norm(item.get("artist", ""))
    score = 0
    if album and _norm(album) and _norm(album) in label:
        score += 3
    if title and _norm(title) and _norm(title) in label:
        score += 2
    if artist and _norm(artist) and _norm(artist) == name:
        score += 4
    return score


def check_token(token: str) -> bool:
    """Return True when Genius accepts the token for search.

    `/account` needs a user OAuth token, so a normal client access token must be
    checked through the search endpoint instead. Network errors propagate.
    """
    if not _clean(token):
        return False
    import urllib.error

    try:
        data = _get_json(
            "https://api.genius.com/search?" + urllib.parse.urlencode({"q": "test"}),
            {"Authorization": f"Bearer {token.strip()}"},
        )
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return False
        raise
    return isinstance(data, dict) and "response" in data


def search(artist: str, album: str, title: str, genius_token: str = "", limit: int = 10) -> list[dict]:
    """Find cover candidates for one track. Network errors simply yield fewer results."""
    artist, album, title = _clean(artist), _clean(album), _clean(title)
    fetchers = [
        lambda: _itunes(artist, album, title),
        lambda: _deezer(artist, album, title),
        lambda: _cover_art_archive(artist, album, title),
        lambda: _genius(artist, album, title, genius_token),
    ]
    candidates = _collect(fetchers)
    candidates.sort(key=lambda item: _score(item, artist, album, title), reverse=True)
    candidates = [item for item in candidates if _score(item, artist, album, title) > 0][:limit]
    if not candidates:
        return []

    results: list[dict | None] = [None] * len(candidates)
    with ThreadPoolExecutor(max_workers=min(6, len(candidates))) as pool:
        futures = [pool.submit(_prepare, item["url"]) for item in candidates]
    for index, future in enumerate(futures):
        try:
            prepared = future.result()
        except Exception:
            continue
        if prepared is None:
            continue
        results[index] = {
            "source": candidates[index]["source"],
            "label": candidates[index]["label"],
            "artist": candidates[index]["artist"],
            "thumb": _as_data_url(prepared["thumb"]),
            "cover": _as_data_url(prepared["cover"]),
        }

    return [item for item in results if item]
