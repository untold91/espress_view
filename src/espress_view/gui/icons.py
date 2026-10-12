"""Small, theme-aware outline icons drawn locally with Pillow."""

from __future__ import annotations

from collections.abc import Callable

from PIL import Image, ImageDraw

ICON_NAMES = ("monitor", "flash", "refresh", "clear", "export", "abort", "expand", "collapse", "browse", "remove")


def render_icon(name: str, color: str, size: tuple[int, int]) -> Image.Image:
    """Render a crisp 24-unit outline icon without external runtime assets."""
    scale = 4
    image = Image.new("RGBA", (24 * scale, 24 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def point(x: float, y: float) -> tuple[int, int]:
        return round(x * scale), round(y * scale)

    def line(points: list[tuple[float, float]], width: float = 1.8) -> None:
        draw.line([point(x, y) for x, y in points], fill=color, width=round(width * scale), joint="curve")

    def rectangle(box: tuple[float, float, float, float], radius: float = 2.0, width: float = 1.8) -> None:
        draw.rounded_rectangle(
            tuple(round(value * scale) for value in box),
            radius=round(radius * scale),
            outline=color,
            width=round(width * scale),
        )

    def arc(box: tuple[float, float, float, float], start: int, end: int, width: float = 1.8) -> None:
        draw.arc(tuple(round(value * scale) for value in box), start, end, fill=color, width=round(width * scale))

    def polygon(points: list[tuple[float, float]]) -> None:
        draw.polygon([point(x, y) for x, y in points], fill=color)

    icons: dict[str, Callable[[], None]] = {
        "monitor": lambda: (
            rectangle((3.5, 4.5, 20.5, 16.5), 2),
            line([(12, 16.5), (12, 19)]),
            line([(8, 20), (16, 20)]),
        ),
        "flash": lambda: polygon([(13.4, 2.7), (6.4, 13), (11.1, 13), (10.2, 21.3), (17.7, 10.2), (13, 10.2)]),
        "refresh": lambda: (
            arc((4.3, 4.3, 19.7, 19.7), 38, 320),
            line([(17.2, 3.9), (19.8, 4.1), (19.5, 6.8)]),
            line([(6.8, 20.1), (4.2, 19.9), (4.5, 17.2)]),
        ),
        "clear": lambda: (
            line([(4, 7), (20, 7)]),
            line([(9, 4), (15, 4)]),
            line([(6.5, 7), (7.5, 20), (16.5, 20), (17.5, 7)]),
            line([(10, 10), (10.5, 17)]),
            line([(14, 10), (13.5, 17)]),
        ),
        "export": lambda: (
            line([(12, 14), (12, 3.5)]),
            line([(8.5, 7), (12, 3.5), (15.5, 7)]),
            line([(5, 13), (5, 19), (19, 19), (19, 13)]),
        ),
        "abort": lambda: (
            arc((3.5, 3.5, 20.5, 20.5), 0, 359),
            line([(8.5, 8.5), (15.5, 15.5)]),
            line([(15.5, 8.5), (8.5, 15.5)]),
        ),
        "expand": lambda: (
            line([(9, 4), (4, 4), (4, 9)]),
            line([(4, 4), (10, 10)]),
            line([(15, 20), (20, 20), (20, 15)]),
            line([(20, 20), (14, 14)]),
        ),
        "collapse": lambda: (
            line([(4, 9), (4, 4), (9, 4)]),
            line([(4, 4), (10, 10)]),
            line([(20, 15), (20, 20), (15, 20)]),
            line([(20, 20), (14, 14)]),
        ),
        "browse": lambda: (
            line([(3, 6), (9, 6), (11, 8), (21, 8), (19.5, 18), (4.5, 18), (3, 6)]),
            line([(3.5, 8), (20.5, 8)]),
        ),
        "remove": lambda: (
            arc((3.5, 3.5, 20.5, 20.5), 0, 359),
            line([(8, 12), (16, 12)]),
        ),
    }
    try:
        icons[name]()
    except KeyError as error:
        raise ValueError(f"Unknown icon: {name}") from error
    return image.resize(size, Image.Resampling.LANCZOS)
