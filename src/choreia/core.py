"""Public API: inspect a file, then rewrite it so one clean tag and one cover survive."""

from __future__ import annotations

from pathlib import Path

from . import flac, mp3, mp4, ogg
from .atomic import write_with_backup
from .detect import detect_container
from .model import FileReport, Picture

BACKENDS = {"mp3": mp3, "flac": flac, "m4a": mp4, "ogg": ogg, "opus": ogg}

SIDECAR_NAMES = {
    "folder.jpg",
    "folder.jpeg",
    "folder.png",
    "cover.jpg",
    "cover.jpeg",
    "cover.png",
    "front.jpg",
    "front.jpeg",
    "album.jpg",
    "albumart.jpg",
    "albumart.png",
}


class UnsupportedFormat(ValueError):
    """The container is not handled by any backend."""


def _backend(code: str):
    module = BACKENDS.get(code)
    if module is None:
        raise UnsupportedFormat(
            f"контейнер «{code}» не поддерживается: работают mp3, flac, m4a, ogg, opus"
        )
    return module


def _sidecar_warnings(path: Path) -> list[str]:
    try:
        names = {entry.name.lower() for entry in path.parent.iterdir() if entry.is_file()}
    except OSError:
        return []
    hits = sorted(names & SIDECAR_NAMES)
    if not hits:
        return []
    return [
        f"рядом лежат файлы обложки ({', '.join(hits)}) — некоторые плееры берут картинку из них, а не из тега"
    ]


def inspect_file(path: Path | str) -> FileReport:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    container = detect_container(path)
    module = _backend(container.code)
    report = module.read(path)
    report.container = container.code
    report.container_note = container.note

    if container.note:
        report.warnings.insert(0, container.note)
    cover = report.front_cover
    if cover is not None and cover.width and cover.height:
        if min(cover.width, cover.height) < 500:
            report.warnings.append(
                f"обложка {cover.resolution} — площадки могут заменить её своей, "
                "лучше от 1000x1000 и больше"
            )
        elif cover.width != cover.height:
            report.warnings.append(f"обложка не квадратная ({cover.resolution}) — площадки обрезают такие")
    report.warnings.extend(_sidecar_warnings(path))
    return report


def clean_file(
    path: Path | str,
    *,
    keep: Picture | None,
    metadata: dict[str, str] | None = None,
    target_id3: int = 3,
    backup: bool = True,
    dry_run: bool = False,
) -> FileReport:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    container = detect_container(path)
    module = _backend(container.code)

    normalized = {name: (value or "").strip() for name, value in (metadata or {}).items()}
    if not dry_run:
        write_with_backup(
            path,
            lambda temporary: module.write(temporary, keep, normalized, target_id3),
            backup=backup,
        )
    return inspect_file(path)
