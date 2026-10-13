"""Persistent settings for the Espress View desktop application."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "theme": "system",
    "flash_baud": "2000000",
    "monitor_baud": "115200",
    "last_view": "monitor",
    "window_width": 1040,
    "window_height": 650,
    "show_flash_logs": False,
    "monitor_auto_scroll": True,
    "monitor_timestamps": False,
    "monitor_log_filename": "esp_monitor.log",
    "flash_log_filename": "esp_flash.log",
}


class AppSettings:
    """Read and save user preferences in a local JSON file."""

    def __init__(self, config_path: Path | None = None) -> None:
        if config_path is None:
            config_path = Path.home() / ".espress_view" / "settings.json"
        self.config_path = config_path
        self._data = dict(DEFAULT_SETTINGS)
        self.last_save_error: Exception | None = None
        self.load()

    def load(self) -> dict[str, object]:
        """Load settings from disk, preserving sane defaults for missing values."""
        if not self.config_path.exists():
            self._data = dict(DEFAULT_SETTINGS)
            return self._data
        try:
            with self.config_path.open("r", encoding="utf-8") as config_file:
                loaded = json.load(config_file)
        except (OSError, ValueError) as error:
            LOGGER.warning("Could not read settings from %s, using defaults: %s", self.config_path, error)
            if not self._data:
                self._data = dict(DEFAULT_SETTINGS)
            return self._data

        merged = dict(DEFAULT_SETTINGS)
        if isinstance(loaded, dict):
            merged.update({key: value for key, value in loaded.items() if value is not None})
        self._data = merged
        return self._data

    def save(self) -> bool:
        """Persist the current settings to disk atomically."""
        temp_file: Path | None = None
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            temp_file = self.config_path.with_name(f"{self.config_path.name}.tmp.{os.getpid()}")
            with temp_file.open("w", encoding="utf-8") as config_file:
                json.dump(self._data, config_file, indent=2, sort_keys=True)
                config_file.flush()
                os.fsync(config_file.fileno())
            temp_file.replace(self.config_path)
            self.last_save_error = None
            return True
        except (OSError, TypeError, ValueError) as error:
            LOGGER.error("Could not persist settings to %s: %s", self.config_path, error)
            self.last_save_error = error
            if temp_file is not None and temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            return False

    def get(self, key: str, default: object | None = None) -> object | None:
        """Return a value from the in-memory settings cache."""
        return self._data.get(key, default)

    def set(self, key: str, value: object) -> bool:
        """Update a setting and flush it to disk."""
        self._data[key] = value
        return self.save()

    @property
    def theme(self) -> str:
        """Return the current user theme preference."""
        theme = str(self.get("theme", DEFAULT_SETTINGS["theme"]))
        return theme if theme in {"dark", "light", "system"} else DEFAULT_SETTINGS["theme"]

    @theme.setter
    def theme(self, value: str) -> None:
        self.set("theme", value)

    @property
    def flash_baud(self) -> str:
        """Return the configured firmware programming baud rate."""
        return str(self.get("flash_baud", DEFAULT_SETTINGS["flash_baud"]))

    @flash_baud.setter
    def flash_baud(self, value: str) -> None:
        self.set("flash_baud", value)

    @property
    def monitor_baud(self) -> str:
        """Return the configured serial-monitor baud rate."""
        return str(self.get("monitor_baud", DEFAULT_SETTINGS["monitor_baud"]))

    @monitor_baud.setter
    def monitor_baud(self, value: str) -> None:
        self.set("monitor_baud", value)

    @property
    def last_view(self) -> str:
        """Return the last application view saved by the user."""
        return str(self.get("last_view", DEFAULT_SETTINGS["last_view"]))

    @last_view.setter
    def last_view(self, value: str) -> None:
        self.set("last_view", value)

    @property
    def window_size(self) -> tuple[int, int]:
        """Return the saved window dimensions, clamped to usable minimums."""
        width = int(self.get("window_width", DEFAULT_SETTINGS["window_width"]))
        height = int(self.get("window_height", DEFAULT_SETTINGS["window_height"]))
        return max(width, 860), max(height, 540)

    @window_size.setter
    def window_size(self, value: tuple[int, int]) -> None:
        self.set("window_width", max(860, value[0]))
        self.set("window_height", max(540, value[1]))

    @property
    def show_flash_logs(self) -> bool:
        """Report whether the flash console should open automatically."""
        value = self.get("show_flash_logs", DEFAULT_SETTINGS["show_flash_logs"])
        return bool(value)

    @show_flash_logs.setter
    def show_flash_logs(self, value: bool) -> None:
        self.set("show_flash_logs", bool(value))

    @property
    def monitor_auto_scroll(self) -> bool:
        """Report whether monitor output should follow newly received data."""
        value = self.get("monitor_auto_scroll", DEFAULT_SETTINGS["monitor_auto_scroll"])
        return bool(value)

    @monitor_auto_scroll.setter
    def monitor_auto_scroll(self, value: bool) -> None:
        self.set("monitor_auto_scroll", bool(value))

    @property
    def monitor_timestamps(self) -> bool:
        """Report whether monitor output should include timestamps."""
        value = self.get("monitor_timestamps", DEFAULT_SETTINGS["monitor_timestamps"])
        return bool(value)

    @monitor_timestamps.setter
    def monitor_timestamps(self, value: bool) -> None:
        self.set("monitor_timestamps", bool(value))

    @property
    def monitor_log_filename(self) -> str:
        """Return the default filename for exported monitor output."""
        return str(self.get("monitor_log_filename", DEFAULT_SETTINGS["monitor_log_filename"]))

    @monitor_log_filename.setter
    def monitor_log_filename(self, value: str) -> None:
        self.set("monitor_log_filename", value)

    @property
    def flash_log_filename(self) -> str:
        """Return the default filename for exported flash output."""
        return str(self.get("flash_log_filename", DEFAULT_SETTINGS["flash_log_filename"]))

    @flash_log_filename.setter
    def flash_log_filename(self, value: str) -> None:
        self.set("flash_log_filename", value)
