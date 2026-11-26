"""Desktop entry point: local server + WebView2 window."""

from __future__ import annotations

import ctypes
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from .library.db import Library
from .library.thumbs import ThumbCache
from .player.server import Server
from .window import find_edge, find_window, focus_window, open_app_window

APP_NAME = "Choreia"
_MUTEX = None
ERROR_ALREADY_EXISTS = 183


def acquire_single_instance() -> bool:
    """One player per user session; a second launch focuses the first window."""
    global _MUTEX
    if sys.platform != "win32":
        return True
    _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\ChoreiaPlayer")
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        hwnd = find_window()
        if hwnd:
            focus_window(hwnd)
        else:
            ctypes.windll.user32.MessageBoxW(
                None,
                "χορεία уже запущена. Найдите окно на панели задач.",
                "χορεία",
                0x40,
            )
        return False
    return True


def configure_logging(directory: Path) -> None:
    try:
        from logging.handlers import RotatingFileHandler

        handler = RotatingFileHandler(
            directory / "choreia.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            handlers=[handler],
        )
    except Exception:
        pass

    def report(exc_type, exc_value, exc_tb):  # noqa: ANN001
        logging.exception("unhandled", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = report


def app_dir() -> Path:
    root = os.getenv("LOCALAPPDATA") or str(Path.home())
    return Path(root) / APP_NAME


def load_credentials(library: Library, directory: Path) -> None:
    """Read an optional credentials.json that stays outside the repository."""
    path = directory / "credentials.json"
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if payload.get("genius_token"):
        library.set_setting("genius_token", str(payload["genius_token"]))


class Bridge:
    """Small JS bridge for things a browser cannot do: native dialogs, Explorer."""

    def __init__(self) -> None:
        self.window = None
        self.library: Library | None = None

    def pick_folder(self):
        import webview

        if self.window is None:
            return None
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        return result[0] if result else None

    def played(self, track_id):  # noqa: ANN001
        if self.library is not None:
            self.library.mark_played(int(track_id))
        return True

    def reveal(self, path):  # noqa: ANN001
        target = Path(str(path))
        if target.exists():
            subprocess.run(["explorer", "/select,", str(target)], check=False)
        return True


def main() -> int:
    directory = app_dir()
    directory.mkdir(parents=True, exist_ok=True)
    configure_logging(directory)
    if not acquire_single_instance():
        return 0
    logging.info("startup: app dir %s", directory)
    library = Library(directory / "library.db")
    thumbs = ThumbCache(directory / "cache" / "thumbs")
    load_credentials(library, directory)

    web_root = Path(__file__).parent / "web"
    server = Server(library, thumbs, web_root).start()
    logging.info("startup: server on port %s", server.port)

    try:
        if find_edge() is not None:
            logging.info("startup: edge window")
            open_app_window(server.url, directory / "edge")
        else:
            logging.info("startup: embedded webview fallback")
            run_embedded(server, library)
    finally:
        server.stop()
        library.close()
    return 0


def run_embedded(server: Server, library: Library) -> None:
    import webview

    bridge = Bridge()
    bridge.library = library
    window = webview.create_window(
        "χορεία",
        server.url,
        width=1280,
        height=840,
        min_size=(1000, 660),
        background_color="#0B0B12",
        js_api=bridge,
    )
    bridge.window = window
    webview.start()


if __name__ == "__main__":
    sys.exit(main())
