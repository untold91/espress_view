"""Tests for persistent application preferences."""

# Test names are descriptive; their imports follow the local src-path bootstrap.
# pylint: disable=duplicate-code,missing-class-docstring,missing-function-docstring,wrong-import-position

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
            self.assertEqual(settings.monitor_log_filename, "esp_monitor.log")
            self.assertEqual(settings.flash_log_filename, "esp_flash.log")

    def test_existing_user_preferences_are_preserved_when_loading_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "settings.json"
            config_path.write_text(
                json.dumps({
                    "theme": "dark",
                    "last_view": "flash",
                    "monitor_baud": "57600",
                    "monitor_log_filename": "custom_monitor.log",
                    "flash_log_filename": "custom_flash.log",
                }),
                encoding="utf-8",
            )

            settings = AppSettings(config_path)

            self.assertEqual(settings.theme, "dark")
            self.assertEqual(settings.last_view, "flash")
            self.assertEqual(settings.monitor_baud, "57600")
            self.assertEqual(settings.flash_baud, "2000000")
            self.assertFalse(settings.show_flash_logs)
            self.assertEqual(settings.monitor_log_filename, "custom_monitor.log")
            self.assertEqual(settings.flash_log_filename, "custom_flash.log")

    def test_invalid_theme_falls_back_to_system(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "settings.json"
            config_path.write_text(json.dumps({"theme": "sepia"}), encoding="utf-8")

            self.assertEqual(AppSettings(config_path).theme, "system")

    def test_atomic_save_writes_and_replaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "settings.json"
            settings = AppSettings(config_path)
            success = settings.set("theme", "dark")

            self.assertTrue(success)
            self.assertIsNone(settings.last_save_error)
            self.assertTrue(config_path.exists())
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["theme"], "dark")

    def test_save_failure_is_captured_and_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            # Point to a path inside an invalid file as directory
            invalid_path = Path(directory) / "a_file"
            invalid_path.write_text("blocker", encoding="utf-8")
            config_path = invalid_path / "settings.json"

            settings = AppSettings(config_path)
            success = settings.save()

            self.assertFalse(success)
            self.assertIsNotNone(settings.last_save_error)

    def test_load_corrupt_json_preserves_valid_defaults_or_in_memory_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "settings.json"
            config_path.write_text("{invalid json", encoding="utf-8")

            settings = AppSettings(config_path)
            self.assertEqual(settings.theme, "system")
            self.assertEqual(settings.monitor_baud, "115200")


if __name__ == "__main__":
    unittest.main()
