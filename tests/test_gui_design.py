"""Tests for the local GUI design assets."""

import unittest

from espress_view.gui.design import COLORS
from espress_view.gui.icons import ICON_NAMES, render_icon


class GuiDesignTests(unittest.TestCase):
    def test_every_icon_renders_with_transparency_and_requested_size(self) -> None:
        for name in ICON_NAMES:
            with self.subTest(icon=name):
                image = render_icon(name, "#20242A", (18, 18))
                self.assertEqual(image.size, (18, 18))
                self.assertEqual(image.mode, "RGBA")
                self.assertGreater(image.getchannel("A").getbbox()[2], 0)

    def test_design_tokens_include_light_and_dark_semantic_colors(self) -> None:
        self.assertEqual(COLORS["window"], ("#F5F6F8", "#17191D"))
        self.assertEqual(COLORS["accent"], ("#2867D8", "#6C9EFF"))
        self.assertEqual(COLORS["accent_text"], ("#FFFFFF", "#17191D"))
        self.assertIn("success", COLORS)
        self.assertIn("warning", COLORS)
        self.assertIn("error", COLORS)

    def test_unknown_icon_names_fail_explicitly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown icon"):
            render_icon("not-an-icon", "#20242A", (18, 18))


if __name__ == "__main__":
    unittest.main()
