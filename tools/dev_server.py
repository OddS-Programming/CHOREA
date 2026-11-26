"""Start the UI server with a demo library and keep it running for inspection."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from choreia.library.db import Library  # noqa: E402
from choreia.library.scanner import Scanner  # noqa: E402
from choreia.library.thumbs import ThumbCache  # noqa: E402
from choreia.player.server import Server  # noqa: E402

BASE = Path(r"C:\Users\maksi\AppData\Local\Temp\opencode\choreia-dev")
DEMO = Path(r"C:\Users\maksi\OneDrive\Desktop\coverfix-demo")


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    database = BASE / "library.db"
    if database.exists():
        database.unlink()
    library = Library(database)
    thumbs = ThumbCache(BASE / "thumbs")
    if DEMO.is_dir():
        print("scan:", Scanner(library, thumbs).scan_folder(DEMO).as_dict(), flush=True)
    server = Server(library, thumbs, ROOT / "src" / "choreia" / "web").start()
    (BASE / "url.txt").write_text(server.url, encoding="utf-8")
    print("URL_WRITTEN", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        library.close()


if __name__ == "__main__":
    main()
