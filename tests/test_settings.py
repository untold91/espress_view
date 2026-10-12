"""Tests for persistent application preferences."""

import json
import tempfile
import unittest
from pathlib import Path

from espress_view.utils.settings import AppSettings


class AppSettingsTests(unittest.TestCase):
    def test_fresh_settings_use_the_required_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = AppSettings(Path(directory) / "settings.json")

            self.assertEqual(settings.last_view, "monitor")
            self.assertEqual(settings.monitor_baud, "115200")
            self.assertEqual(settings.flash_baud, "2000000")
            self.assertEqual(settings.theme, "system")
            self.assertFalse(settings.show_flash_logs)

    def test_existing_user_preferences_are_preserved_when_loading_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "settings.json"
            config_path.write_text(
                json.dumps({"theme": "dark", "last_view": "flash", "monitor_baud": "57600"}),
                encoding="utf-8",
            )

            settings = AppSettings(config_path)

            self.assertEqual(settings.theme, "dark")
            self.assertEqual(settings.last_view, "flash")
            self.assertEqual(settings.monitor_baud, "57600")
            self.assertEqual(settings.flash_baud, "2000000")
            self.assertFalse(settings.show_flash_logs)

    def test_invalid_theme_falls_back_to_system(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "settings.json"
            config_path.write_text(json.dumps({"theme": "sepia"}), encoding="utf-8")

            self.assertEqual(AppSettings(config_path).theme, "system")


if __name__ == "__main__":
    unittest.main()
