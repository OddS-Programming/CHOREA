"""Open the UI in a Chromium app window (Edge) instead of embedding WebView2.

The embedded WebView2 route goes through pythonnet and WinForms, which freezes
the window on some machines during .NET accessibility queries. Edge's --app
window uses the same engine without that layer.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

TITLE_HINT = "χορεία"
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


def find_edge() -> Path | None:
    roots = [
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
        Path(os.environ.get("LOCALAPPDATA", "")),
    ]
    for root in roots:
        candidate = root / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        if candidate.exists():
            return candidate
    return None


def _windows() -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []

    def callback(hwnd, _param):  # noqa: ANN001
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length:
            buffer = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
            found.append((int(hwnd), buffer.value))
        return True

    if sys.platform == "win32":
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), 0)
    return found


def find_window(hint: str = TITLE_HINT) -> int:
    for hwnd, title in _windows():
        if hint in title:
            return hwnd
    return 0


def focus_window(hwnd: int) -> None:
    if not hwnd:
        return
    ctypes.windll.user32.ShowWindow(hwnd, 9)
    ctypes.windll.user32.SetForegroundWindow(hwnd)


def open_app_window(url: str, profile: Path, width: int = 1280, height: int = 840) -> None:
    edge = find_edge()
    if edge is None:
        raise FileNotFoundError("Microsoft Edge not found")
    profile.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            str(edge),
            f"--app={url}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={width},{height}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + 20
    while time.time() < deadline and not find_window():
        if process.poll() is not None and not find_window():
            time.sleep(0.3)
            break
        time.sleep(0.25)

    while find_window():
        time.sleep(1.0)
