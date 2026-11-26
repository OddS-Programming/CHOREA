"""Generate the tiny audio fixtures used by the test suite.

Run once: .venv/Scripts/python.exe tools/make_assets.py
The generated files are committed, so tests never need ffmpeg.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg

ASSETS = Path(__file__).resolve().parents[1] / "tests" / "assets"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def make(name: str, codec: str, *extra: str) -> None:
    target = ASSETS / name
    command = [
        FFMPEG,
        "-y",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=44100:cl=stereo",
        "-t",
        "0.4",
        "-c:a",
        codec,
        *extra,
        str(target),
    ]
    subprocess.run(command, check=True)
    print(f"{name}: {target.stat().st_size} bytes")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    make("tone.mp3", "libmp3lame", "-b:a", "64k", "-id3v2_version", "3")
    make("tone.flac", "flac")
    make("tone.m4a", "aac", "-b:a", "64k")
    make("tone.ogg", "libvorbis", "-q:a", "0")


if __name__ == "__main__":
    main()
