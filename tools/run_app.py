"""PyInstaller entry point for the player."""

import os
import sys
import traceback
from pathlib import Path


def _crash_log() -> Path:
    root = Path(os.getenv("LOCALAPPDATA") or Path.home()) / "Choreia"
    root.mkdir(parents=True, exist_ok=True)
    return root / "crash.txt"


def main() -> int:
    try:
        from choreia.app import main as run

        return run()
    except BaseException:
        try:
            _crash_log().write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    sys.exit(main())
