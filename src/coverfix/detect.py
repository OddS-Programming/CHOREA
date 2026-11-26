"""Identify the real container from magic bytes, never from the extension."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

EXTENSION_CONTAINERS = {
    ".mp3": "mp3",
    ".mp2": "mp3",
    ".flac": "flac",
    ".m4a": "m4a",
    ".m4b": "m4a",
    ".mp4": "m4a",
    ".aac": "m4a",
    ".ogg": "ogg",
    ".oga": "ogg",
    ".opus": "opus",
    ".wav": "wav",
    ".mkv": "matroska",
    ".webm": "matroska",
}

MATROSKA_NOTE = (
    "Matroska/WebM: это не аудиоконтейнер с тегами — обложка может быть "
    "в видеопотоке, правка тегов её не изменит"
)


@dataclass(frozen=True)
class Container:
    code: str
    note: str = ""


def _detect(head: bytes) -> str:
    if head[:3] == b"ID3":
        return "mp3"
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return "mp3"
    if head[:4] == b"fLaC":
        return "flac"
    if head[:4] == b"OggS":
        return "opus" if b"OpusHead" in head else "ogg"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[4:8] == b"ftyp":
        return "m4a"
    if head[:4] == b"\x1aE\xdf\xa3":
        return "matroska"
    return "unknown"


def detect_container(path: Path) -> Container:
    path = Path(path)
    with path.open("rb") as handle:
        head = handle.read(4096)

    code = _detect(head)
    extension = path.suffix.lower()
    expected = EXTENSION_CONTAINERS.get(extension)

    if code == "matroska":
        return Container(code, MATROSKA_NOTE)
    if expected and code != "unknown" and expected != code:
        if not (expected == "opus" and code == "ogg"):
            return Container(code, f"расширение {extension} не соответствует контейнеру {code}")
    return Container(code, "")
