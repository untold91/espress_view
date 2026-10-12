"""Tests for the local GUI design assets."""

import unittest

from espress_view.gui.design import COLORS
from espress_view.gui.icons import ICON_NAMES, load_icon


def _contrast_ratio(first: str, second: str) -> float:
    def luminance(value: str) -> float:
        channels = [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return sum(weight * channel for weight, channel in zip((0.2126, 0.7152, 0.0722), linear))

    bright, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


class GuiDesignTests(unittest.TestCase):
    def test_every_icon_renders_with_transparency_and_requested_size(self) -> None:
        for name in ICON_NAMES:
            with self.subTest(icon=name):
                image = load_icon(name, "#20242A", (18, 18))
                self.assertEqual(image.size, (18, 18))
                self.assertEqual(image.mode, "RGBA")
                self.assertGreater(image.getchannel("A").getbbox()[2], 0)
                opaque_pixel = max(image.getdata(), key=lambda pixel: pixel[3])
                self.assertEqual(opaque_pixel[:3], (32, 36, 42))

    def test_design_tokens_include_light_and_dark_semantic_colors(self) -> None:
        self.assertEqual(COLORS["window"], ("#F0F1F3", "#17191D"))
        self.assertEqual(COLORS["sidebar"], ("#E8EAED", "#1B1E23"))
        self.assertEqual(COLORS["surface"], ("#FAFAF8", "#20242A"))
        self.assertEqual(COLORS["surface_alt"], ("#F1F2F0", "#262B32"))
        self.assertEqual(COLORS["accent"], ("#315FA8", "#6C9EFF"))
        self.assertEqual(COLORS["accent_text"], ("#FFFFFF", "#17191D"))
        self.assertIn("input", COLORS)
        self.assertIn("success", COLORS)
        self.assertIn("warning", COLORS)
        self.assertIn("error", COLORS)

    def test_light_theme_text_and_status_colors_meet_aa_contrast(self) -> None:
        for token in ("text", "text_secondary", "text_muted", "success", "warning", "error"):
            with self.subTest(token=token):
                self.assertGreaterEqual(_contrast_ratio(COLORS[token][0], COLORS["surface"][0]), 4.5)
        self.assertGreaterEqual(
            _contrast_ratio(COLORS["accent_text"][0], COLORS["accent"][0]),
            4.5,
        )

    def test_unknown_icon_names_fail_explicitly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown icon"):
            load_icon("not-an-icon", "#20242A", (18, 18))


if __name__ == "__main__":
    unittest.main()
