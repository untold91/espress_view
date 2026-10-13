"""Tests for the AppearanceSelector component."""

# Test names are descriptive, and GUI tests intentionally inspect widget internals.
# pylint: disable=duplicate-code,missing-class-docstring,missing-function-docstring,protected-access,wrong-import-position

import sys
import unittest
from tkinter import TclError
from pathlib import Path
from unittest.mock import Mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import customtkinter as ctk
from espress_view.gui.appearance import AppearanceSelector


class AppearanceSelectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = ctk.CTk()
        self.root.withdraw()

    def tearDown(self) -> None:
        try:
            self.root.update_idletasks()
        except TclError:
            pass
        self.root.destroy()

    def test_appearance_selector_creates_three_modes(self) -> None:
        dummy_img = ctk.CTkImage(Image.new("RGBA", (18, 18)), size=(18, 18))
        theme_var = ctk.StringVar(value="system")
        icons = {"sun": dummy_img, "monitor": dummy_img, "moon": dummy_img}
        on_change = Mock()
        add_tooltip = Mock()
        add_focus_indicator = Mock()

        selector = AppearanceSelector(
            self.root,
            theme_var=theme_var,
            icons=icons,
            on_change=on_change,
            add_tooltip=add_tooltip,
            add_focus_indicator=add_focus_indicator,
        )

        self.assertEqual(set(selector.buttons.keys()), {"light", "system", "dark"})
        self.assertEqual(add_tooltip.call_count, 3)
        self.assertEqual(add_focus_indicator.call_count, 3)

        # Test clicking light button
        selector._handle_click("light")
        on_change.assert_called_once_with("light")

        # Test sync highlights the active mode
        theme_var.set("dark")
        selector.sync()
        dark_btn = selector.buttons["dark"]
        light_btn = selector.buttons["light"]
        self.assertNotEqual(dark_btn.cget("fg_color"), "transparent")
        self.assertEqual(light_btn.cget("fg_color"), "transparent")


if __name__ == "__main__":
    unittest.main()
