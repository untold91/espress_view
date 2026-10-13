"""Tests for the ChevronOptionMenu custom widget."""

# Test names are descriptive, and GUI tests intentionally inspect widget internals.
# pylint: disable=duplicate-code,missing-class-docstring,missing-function-docstring,protected-access,wrong-import-position

import sys
import unittest
from pathlib import Path
from tkinter import TclError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import customtkinter as ctk
from espress_view.gui.widgets import ChevronOptionMenu


class ChevronOptionMenuTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = ctk.CTk()
        self.root.withdraw()

    def tearDown(self) -> None:
        try:
            self.root.update_idletasks()
        except TclError:
            pass
        self.root.destroy()

    def test_chevron_option_menu_initializes_and_draws(self) -> None:
        variable = ctk.StringVar(value="Option 1")
        menu = ChevronOptionMenu(self.root, variable=variable, values=["Option 1", "Option 2"])
        menu._draw()
        self.assertIsNotNone(menu._chevron_image)

    def test_chevron_option_menu_disabled_state(self) -> None:
        variable = ctk.StringVar(value="Option 1")
        menu = ChevronOptionMenu(self.root, variable=variable, values=["Option 1", "Option 2"], state="disabled")
        menu._draw()
        # Hovering while disabled does not crash
        menu._on_chevron_enter()
        menu._on_chevron_leave()

    def test_chevron_option_menu_hover_events(self) -> None:
        variable = ctk.StringVar(value="Option 1")
        menu = ChevronOptionMenu(self.root, variable=variable, values=["Option 1", "Option 2"])
        menu._on_chevron_enter()
        menu._on_chevron_leave()


if __name__ == "__main__":
    unittest.main()
