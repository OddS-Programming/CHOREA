"""Write through a temporary copy so a failure can never damage the original."""

from __future__ import annotations

import os
import shutil
import stat
import time
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


def _windows_replace(temporary: Path, target: Path) -> bool:
    """Swap files through ReplaceFileW, the one API that works while a reader streams."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        replace_file = kernel32.ReplaceFileW
        replace_file.restype = wintypes.BOOL
        replace_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.LPVOID,
        ]
        return bool(replace_file(str(target), str(temporary), None, 0, None, None))
    except (ImportError, OSError, ValueError):
        return False


def _swap_in(temporary: Path, target: Path) -> None:
    """Replace `target` with `temporary`, tolerating readers and indexers."""
    last_error: OSError | None = None
    for attempt in range(3):
        try:
            os.replace(temporary, target)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.06 * (attempt + 1))
    if _windows_replace(temporary, target):
        return
    assert last_error is not None
    raise last_error


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
        _swap_in(temporary, path)
    except BaseException:
        _discard(temporary)
        raise
