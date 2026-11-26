"""Desktop entry point: local server + WebView2 window."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from .library.db import Library
from .library.thumbs import ThumbCache
from .player.server import Server

APP_NAME = "Choreia"


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
    import webview

    directory = app_dir()
    directory.mkdir(parents=True, exist_ok=True)
    library = Library(directory / "library.db")
    thumbs = ThumbCache(directory / "cache" / "thumbs")
    load_credentials(library, directory)

    web_root = Path(__file__).parent / "web"
    server = Server(library, thumbs, web_root).start()

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

    try:
        webview.start()
    finally:
        server.stop()
        library.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
