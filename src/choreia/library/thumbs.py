"""Cover thumbnail cache: keeps the original image and renders any size on demand."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageOps


class ThumbCache:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def digest(data: bytes) -> str:
        return hashlib.sha1(data).hexdigest()

    def path(self, digest: str, size: int) -> Path:
        return self.root / f"{digest}-{size}.jpg"

    def source(self, digest: str) -> Path:
        return self.root / f"{digest}.src"

    def _render(self, digest: str, size: int) -> Path | None:
        target = self.path(digest, size)
        if target.exists() and target.stat().st_size > 0:
            return target
        origin = self.source(digest)
        if not origin.exists():
            return None
        try:
            with Image.open(origin) as image:
                fitted = ImageOps.fit(image.convert("RGB"), (size, size), Image.LANCZOS)
                fitted.save(target, "JPEG", quality=86, optimize=True)
        except Exception:
            target.unlink(missing_ok=True)
            return None
        return target

    def ensure(self, data: bytes, size: int = 320) -> tuple[str, Path]:
        digest = self.digest(data)
        origin = self.source(digest)
        if not origin.exists() or origin.stat().st_size == 0:
            origin.write_bytes(data)
        path = self._render(digest, size) or self.path(digest, size)
        return digest, path

    def store(self, data: bytes) -> str:
        return self.ensure(data, 320)[0]

    def find(self, digest: str | None, size: int = 320) -> Path | None:
        if not digest:
            return None
        for candidate in (size, 320, 64):
            path = self._render(digest, candidate)
            if path is not None:
                return path
        return None
