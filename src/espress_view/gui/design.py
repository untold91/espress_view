"""Shared visual tokens for the Espress View interface."""

from __future__ import annotations

from typing import Final

ColorPair = tuple[str, str]

COLORS: Final[dict[str, ColorPair]] = {
    "window": ("#F0F1F3", "#17191D"),
    "sidebar": ("#E8EAED", "#1B1E23"),
    "surface": ("#FAFAF8", "#20242A"),
    "surface_alt": ("#F1F2F0", "#262B32"),
    "input": ("#FFFFFF", "#20242A"),
    "text": ("#252A31", "#F2F4F7"),
    "text_secondary": ("#505966", "#A6AFBC"),
    "text_muted": ("#66707D", "#7F8997"),
    "border": ("#B9C0C9", "#353B44"),
    "accent": ("#315FA8", "#6C9EFF"),
    "accent_hover": ("#274F90", "#83AEFF"),
    "accent_subtle": ("#E0E8F5", "#29374C"),
    "accent_text": ("#FFFFFF", "#17191D"),
    "success": ("#147A54", "#46B881"),
    "warning": ("#966400", "#E9B65A"),
    "error": ("#C53742", "#F07178"),
    "terminal": ("#F2F3F1", "#171A1F"),
    "terminal_text": ("#29313B", "#D5DBE5"),
    "disabled": ("#E4E6E8", "#30353D"),
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
