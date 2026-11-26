"""Byte-level scan for tag regions that high-level parsers hide.

An mp3 file can carry more than one tag: ID3v2 at the start, a second ID3v2 at
the end, an APEv2 block and an ID3v1 trailer. Most editors show one of them and
silently ignore the rest.

Only the head and the tail window are read, so a 200 MB file does not have to
fit in memory.
"""

from __future__ import annotations

from pathlib import Path

from .model import Region

TAIL_WINDOW = 16 * 1024 * 1024


def _syncsafe(raw: bytes) -> int:
    return (raw[0] & 0x7F) << 21 | (raw[1] & 0x7F) << 14 | (raw[2] & 0x7F) << 7 | (raw[3] & 0x7F)


def _id3v2_total_size(data: bytes, offset: int) -> int | None:
    if data[offset : offset + 3] != b"ID3" or offset + 10 > len(data):
        return None
    major = data[offset + 3]
    revision = data[offset + 4]
    flags = data[offset + 5]
    if major not in (2, 3, 4) or revision == 0xFF:
        return None
    total = 10 + _syncsafe(data[offset + 6 : offset + 10])
    if flags & 0x10:  # footer present
        total += 10
    return total


def _find_trailing_id3v2(data: bytes, end: int) -> Region | None:
    cursor = end
    while cursor > 0:
        position = data.rfind(b"ID3", 0, cursor)
        if position < 0:
            return None
        total = _id3v2_total_size(data, position)
        if total is not None and position + total == end:
            return Region("id3v2", "end", position, total)
        cursor = position
    return None


def scan_mp3_regions(path: Path) -> list[Region]:
    """Return every tag region in an mp3 file, ordered by absolute offset."""
    path = Path(path)
    size = path.stat().st_size
    if size == 0:
        return []

    regions: list[Region] = []

    with path.open("rb") as handle:
        head = handle.read(10)
        leading = _id3v2_total_size(head, 0)
        if leading is not None and leading <= size:
            regions.append(Region("id3v2", "start", 0, leading))

        window_start = max(0, size - TAIL_WINDOW)
        handle.seek(window_start)
        tail = handle.read()

    base = window_start
    end = len(tail)

    if end >= 128 and tail[end - 128 : end - 125] == b"TAG":
        regions.append(Region("id3v1", "end", base + end - 128, 128))
        end -= 128

    if end >= 32 and tail[end - 32 : end - 24] == b"APETAGEX":
        ape_size = int.from_bytes(tail[end - 32 + 12 : end - 32 + 16], "little")
        if 32 <= ape_size <= base + end:
            regions.append(Region("apev2", "end", base + end - ape_size, ape_size))
            end -= ape_size

    trailing = _find_trailing_id3v2(tail, end)
    if trailing is not None:
        regions.append(Region("id3v2", "end", base + trailing.offset, trailing.size))

    unique: dict[tuple[int, int, str], Region] = {}
    for region in regions:
        unique[(region.offset, region.size, region.kind)] = region
    return sorted(unique.values(), key=lambda region: region.offset)
