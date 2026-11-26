"""Data model shared by every format backend."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

PICTURE_TYPE_NAMES = {
    0: "Other",
    1: "File Icon",
    2: "Other File Icon",
    3: "Front Cover",
    4: "Back Cover",
    5: "Leaflet Page",
    6: "Media",
    7: "Lead Artist",
    8: "Artist",
    9: "Conductor",
    10: "Band",
    11: "Composer",
    12: "Lyricist",
    13: "Recording Location",
    14: "During Recording",
    15: "During Performance",
    16: "Screen Capture",
    17: "Bright Coloured Fish",
    18: "Illustration",
    19: "Band Logotype",
    20: "Publisher Logotype",
}

FIELD_LABELS = {
    "title": "Название",
    "artist": "Исполнитель",
    "album": "Альбом",
    "album_artist": "Исполнитель альбома",
    "track": "Трек",
    "disc": "Диск",
    "year": "Год",
    "genre": "Жанр",
}


def guess_mime(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"BM"):
        return "image/bmp"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def image_size(data: bytes) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            return image.size
    except Exception:
        return (None, None)


@dataclass(frozen=True)
class Picture:
    index: int
    type: int
    mime: str
    desc: str
    data: bytes
    width: int | None = None
    height: int | None = None
    source: str = ""

    @property
    def size(self) -> int:
        return len(self.data)

    @property
    def type_name(self) -> str:
        return PICTURE_TYPE_NAMES.get(int(self.type), f"Type {int(self.type)}")

    @property
    def resolution(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "?"

    @property
    def extension(self) -> str:
        return {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/bmp": "bmp"}.get(
            self.mime, "bin"
        )

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "type": int(self.type),
            "type_name": self.type_name,
            "mime": self.mime,
            "desc": self.desc,
            "size": self.size,
            "width": self.width,
            "height": self.height,
            "source": self.source,
        }


def make_picture(
    index: int,
    data: bytes,
    *,
    type: int = 3,
    mime: str = "",
    desc: str = "",
    width: int | None = None,
    height: int | None = None,
    source: str = "",
) -> Picture:
    """Build a Picture, filling MIME and dimensions when the container has none."""
    resolved_mime = mime or guess_mime(data)
    if width is None or height is None:
        measured = image_size(data)
        width = width if width is not None else measured[0]
        height = height if height is not None else measured[1]
    return Picture(
        index=index,
        type=int(type),
        mime=resolved_mime,
        desc=desc,
        data=data,
        width=width,
        height=height,
        source=source,
    )


@dataclass(frozen=True)
class Region:
    kind: str
    position: str
    offset: int
    size: int

    def to_dict(self) -> dict:
        return {"kind": self.kind, "position": self.position, "offset": self.offset, "size": self.size}


@dataclass
class FileReport:
    path: Path
    container: str
    container_note: str = ""
    audio: dict = field(default_factory=dict)
    tag_versions: list[str] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)
    pictures: list[Picture] = field(default_factory=list)
    tags: dict[str, list[str]] = field(default_factory=dict)
    fields: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def front_cover(self) -> Picture | None:
        for picture in self.pictures:
            if int(picture.type) == 3:
                return picture
        return self.pictures[0] if self.pictures else None

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "container": self.container,
            "container_note": self.container_note,
            "audio": self.audio,
            "tag_versions": self.tag_versions,
            "regions": [region.to_dict() for region in self.regions],
            "pictures": [picture.to_dict() for picture in self.pictures],
            "tags": self.tags,
            "fields": self.fields,
            "warnings": self.warnings,
        }
