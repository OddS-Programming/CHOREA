"""Draw the application icon: a violet record on a dark rounded tile."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
OUT = Path(__file__).resolve().parents[1] / "assets" / "app.ico"


def main() -> None:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=SIZE // 5, fill=(15, 15, 18, 255))

    margin = SIZE * 0.14
    disc = (margin, margin, SIZE - margin, SIZE - margin)
    draw.ellipse(disc, fill=(139, 92, 246, 255))
    draw.ellipse((margin * 1.6, margin * 1.6, SIZE - margin * 1.6, SIZE - margin * 1.6), fill=(124, 58, 237, 255))

    centre = SIZE / 2
    for step in range(3, 0, -1):
        radius = SIZE * 0.09 * step + SIZE * 0.06
        draw.ellipse(
            (centre - radius, centre - radius, centre + radius, centre + radius),
            outline=(24, 24, 34, 200),
            width=max(4, SIZE // 110),
        )

    dot = SIZE * 0.055
    draw.ellipse((centre - dot, centre - dot, centre + dot, centre + dot), fill=(242, 242, 246, 255))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        OUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"{OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
