"""Write through a temporary copy so a failure can never damage the original."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path
from typing import Callable


def backup_path(path: Path) -> Path:
    path = Path(path)
    return path.with_name(path.name + ".bak")


def _discard(path: Path) -> None:
    """Remove a scratch file even when it inherited the read-only attribute."""
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)
        path.unlink(missing_ok=True)


def write_with_backup(
    path: Path,
    writer: Callable[[Path], None],
    *,
    backup: bool = True,
) -> None:
    """Run `writer` on a temp copy, then swap it in. Keep a .bak of the original."""
    path = Path(path)
    if not os.access(path, os.W_OK):
        raise PermissionError(f"файл только для чтения: {path.name}")

    if backup:
        saved = backup_path(path)
        if not saved.exists():
            shutil.copy2(path, saved)

    temporary = path.with_name(path.name + ".choreia-tmp")
    shutil.copy2(path, temporary)
    try:
        writer(temporary)
    except BaseException:
        _discard(temporary)
        raise

    try:
        os.replace(temporary, path)
    except BaseException:
        _discard(temporary)
        raise
