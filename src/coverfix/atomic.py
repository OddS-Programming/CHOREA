"""Write through a temporary copy so a failure can never damage the original."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable


def backup_path(path: Path) -> Path:
    path = Path(path)
    return path.with_name(path.name + ".bak")


def write_with_backup(
    path: Path,
    writer: Callable[[Path], None],
    *,
    backup: bool = True,
) -> None:
    """Run `writer` on a temp copy, then swap it in. Keep a .bak of the original."""
    path = Path(path)
    if backup:
        saved = backup_path(path)
        if not saved.exists():
            shutil.copy2(path, saved)

    temporary = path.with_name(path.name + ".coverfix-tmp")
    shutil.copy2(path, temporary)
    try:
        writer(temporary)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

    try:
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
