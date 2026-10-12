"""Load bundled Lucide icons and tint them for the active interface theme."""

from __future__ import annotations

from PIL import Image

from espress_view.utils.paths import resource_path

ICON_NAMES = (
    "sun",
    "monitor",
    "moon",
    "zap",
    "refresh-cw",
    "plug",
    "unplug",
    "folder-open",
    "save",
    "trash-2",
    "circle-x",
    "chevron-up",
    "chevron-down",
    "circle-check",
    "circle-alert",
)


def load_icon(name: str, color: str, size: tuple[int, int]) -> Image.Image:
    """Load a bundled Lucide PNG, tinting its alpha mask for the requested theme."""
    if name not in ICON_NAMES:
        raise ValueError(f"Unknown icon: {name}")

    asset = resource_path("icons", f"lucide-{name}.png")
    with Image.open(asset) as source:
        alpha = source.convert("RGBA").getchannel("A").resize(size, Image.Resampling.LANCZOS)
    image = Image.new("RGBA", size, color)
    image.putalpha(alpha)
    return image
