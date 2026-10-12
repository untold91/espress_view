"""Shared visual tokens for the Espress View interface."""

from __future__ import annotations

from typing import Final

ColorPair = tuple[str, str]

COLORS: Final[dict[str, ColorPair]] = {
    "window": ("#F5F6F8", "#17191D"),
    "sidebar": ("#EEF0F3", "#1B1E23"),
    "surface": ("#FFFFFF", "#20242A"),
    "surface_alt": ("#FFFFFF", "#262B32"),
    "text": ("#20242A", "#F2F4F7"),
    "text_secondary": ("#5F6875", "#A6AFBC"),
    "text_muted": ("#7B8491", "#7F8997"),
    "border": ("#DDE1E7", "#353B44"),
    "accent": ("#2867D8", "#6C9EFF"),
    "accent_hover": ("#1E56BB", "#83AEFF"),
    "accent_subtle": ("#E3ECFC", "#29374C"),
    "accent_text": ("#FFFFFF", "#17191D"),
    "success": ("#16845B", "#46B881"),
    "warning": ("#966400", "#E9B65A"),
    "error": ("#C53742", "#F07178"),
    "terminal": ("#F8F9FB", "#171A1F"),
    "terminal_text": ("#27313F", "#D5DBE5"),
    "disabled": ("#E8EBF0", "#30353D"),
}

FONT_FAMILY: Final = "Segoe UI"
MONOSPACE_FAMILY: Final = "Consolas"

SPACE_XS: Final = 4
SPACE_SM: Final = 8
SPACE_MD: Final = 12
SPACE_LG: Final = 16
SPACE_XL: Final = 24


def color(name: str) -> ColorPair:
    """Return a CustomTkinter light/dark color pair."""
    return COLORS[name]
