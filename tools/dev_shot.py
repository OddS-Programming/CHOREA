"""Render the web UI to a PNG with headless Edge, for visual checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from choreia.library.db import Library  # noqa: E402
from choreia.library.scanner import Scanner  # noqa: E402
from choreia.library.thumbs import ThumbCache  # noqa: E402
from choreia.player.server import Server  # noqa: E402

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = Path(r"C:\Users\maksi\AppData\Local\Temp\opencode\choreia-ui")
DEMO = Path(r"C:\Users\maksi\OneDrive\Desktop\coverfix-demo")


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    database = BASE / "library.db"
    if database.exists():
        database.unlink()
    library = Library(database)
    thumbs = ThumbCache(BASE / "thumbs")
    if DEMO.is_dir():
        print("scan:", Scanner(library, thumbs).scan_folder(DEMO).as_dict())
    server = Server(library, thumbs, ROOT / "src" / "choreia" / "web").start()
    output = BASE / "ui.png"
    profile = BASE / "edge-profile"
    subprocess.run(
        [
            EDGE,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile}",
            "--hide-scrollbars",
            "--window-size=1280,900",
            "--virtual-time-budget=8000",
            "--run-all-compositor-stages-before-draw",
            f"--screenshot={output}",
            server.url,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(output, output.exists())
    server.stop()
    library.close()


if __name__ == "__main__":
    main()
