"""Cover thumbnail cache: one JPEG per image hash and size."""

from __future__ import annotations

import hashlib
import io
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

    def ensure(self, data: bytes, size: int = 320) -> tuple[str, Path]:
        digest = self.digest(data)
        target = self.path(digest, size)
        if target.exists() and target.stat().st_size > 0:
            return digest, target
        try:
            with Image.open(io.BytesIO(data)) as image:
                image = image.convert("RGB")
                fitted = ImageOps.fit(image, (size, size), Image.LANCZOS)
                fitted.save(target, "JPEG", quality=86, optimize=True)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return digest, target

    def find(self, digest: str | None, size: int = 320) -> Path | None:
        if not digest:
            return None
        candidate = self.path(digest, size)
        return candidate if candidate.exists() else None
