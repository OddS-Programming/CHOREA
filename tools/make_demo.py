"""Build a small demo album so the window can be tried without real music.

Run: .venv/Scripts/python.exe tools/make_demo.py
Creates ../choreia-demo with six tracks, tags and covers.
"""

from __future__ import annotations

import io
import math
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from choreia.core import clean_file  # noqa: E402
from choreia.model import make_picture  # noqa: E402

TARGET = Path(__file__).resolve().parents[2] / "choreia-demo"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

TRACKS = [
    ("01 Полярный день", "Северный шум", "Долгая дорога", 133, (74, 82, 160), (28, 30, 60)),
    ("02 Тихий канал", "Северный шум", "Долгая дорога", 187, (150, 92, 140), (40, 24, 48)),
    ("03 Стекло", "Мокрый асфальт", "Городские записи", 96, (60, 130, 130), (18, 34, 36)),
    ("04 Ночная смена", "Мокрый асфальт", "Городские записи", 214, (190, 120, 70), (44, 28, 16)),
    ("05 Воздух", "Пыль", "Первый снег", 61, (120, 160, 200), (24, 34, 44)),
    ("06 Возвращение", "Пыль", "Первый снег", 158, (170, 170, 90), (36, 36, 18)),
]


def cover(width: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (width, width))
    pixels = image.load()
    for y in range(width):
        ratio = y / max(width - 1, 1)
        colour = tuple(round(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        for x in range(width):
            pixels[x, y] = colour
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    centre = width / 2
    for ring in range(6, 0, -1):
        radius = width * ring / 14
        draw.ellipse(
            (centre - radius, centre - radius, centre + radius, centre + radius),
            outline=(255, 255, 255, 12),
            width=max(2, width // 120),
        )
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88)
    return buffer.getvalue()


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for index, (title, artist, album, seconds, top, bottom) in enumerate(TRACKS, start=1):
        target = TARGET / f"{index:02d}.mp3"
        if not target.exists():
            subprocess.run(
                [
                    FFMPEG,
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    f"sine=frequency={220 + index * 40}:duration={seconds}",
                    "-af",
                    "volume=0.08",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    str(target),
                ],
                check=True,
            )
        size = 600 if index % 2 else 480
        picture = make_picture(0, cover(size, top, bottom), type=3)
        clean_file(
            target,
            keep=picture,
            metadata={
                "title": title,
                "artist": artist,
                "album": album,
                "album_artist": artist,
                "track": f"{index}/{len(TRACKS)}",
                "year": "2026",
                "genre": "Ambient",
            },
        )
        print(f"{target.name}: {title} — {artist}")
    print(f"\nГотово: {TARGET}")


if __name__ == "__main__":
    main()
