"""Persistent settings for the Espress View desktop application."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_SETTINGS = {
    "theme": "dark",
    "flash_baud": "2000000",
    "monitor_baud": "115200",
    "last_view": "monitor",
    "window_width": 1040,
    "window_height": 650,
    "show_flash_logs": False,
    "monitor_auto_scroll": True,
    "monitor_timestamps": False,
}


class AppSettings:
    """Read and save user preferences in a local JSON file."""

    def __init__(self, config_path: Path | None = None) -> None:
        if config_path is None:
            config_path = Path.home() / ".espress_view" / "settings.json"
        self.config_path = config_path
        self._data = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> dict[str, object]:
        """Load settings from disk, preserving sane defaults for missing values."""
        if not self.config_path.exists():
            self._data = dict(DEFAULT_SETTINGS)
            return self._data
        try:
            with self.config_path.open("r", encoding="utf-8") as config_file:
                loaded = json.load(config_file)
        except (OSError, ValueError):
            self._data = dict(DEFAULT_SETTINGS)
            return self._data

        merged = dict(DEFAULT_SETTINGS)
        if isinstance(loaded, dict):
            merged.update({key: value for key, value in loaded.items() if value is not None})
        self._data = merged
        return self._data

    def save(self) -> None:
        """Persist the current settings to disk."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.config_path.open("w", encoding="utf-8") as config_file:
                json.dump(self._data, config_file, indent=2, sort_keys=True)
        except OSError:
            return

    def get(self, key: str, default: object | None = None) -> object | None:
        """Return a value from the in-memory settings cache."""
        return self._data.get(key, default)

    def set(self, key: str, value: object) -> None:
        """Update a setting and flush it to disk."""
        self._data[key] = value
        self.save()

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
        return str(self.get("flash_baud", DEFAULT_SETTINGS["flash_baud"]))

    @flash_baud.setter
    def flash_baud(self, value: str) -> None:
        self.set("flash_baud", value)

    @property
    def monitor_baud(self) -> str:
        return str(self.get("monitor_baud", DEFAULT_SETTINGS["monitor_baud"]))

    @monitor_baud.setter
    def monitor_baud(self, value: str) -> None:
        self.set("monitor_baud", value)

    @property
    def last_view(self) -> str:
        return str(self.get("last_view", DEFAULT_SETTINGS["last_view"]))

    @last_view.setter
    def last_view(self, value: str) -> None:
        self.set("last_view", value)

    @property
    def window_size(self) -> tuple[int, int]:
        width = int(self.get("window_width", DEFAULT_SETTINGS["window_width"]))
        height = int(self.get("window_height", DEFAULT_SETTINGS["window_height"]))
        return max(width, 860), max(height, 540)

    @window_size.setter
    def window_size(self, value: tuple[int, int]) -> None:
        self.set("window_width", max(860, value[0]))
        self.set("window_height", max(540, value[1]))

    @property
    def show_flash_logs(self) -> bool:
        value = self.get("show_flash_logs", DEFAULT_SETTINGS["show_flash_logs"])
        return bool(value)

    @show_flash_logs.setter
    def show_flash_logs(self, value: bool) -> None:
        self.set("show_flash_logs", bool(value))

    @property
    def monitor_auto_scroll(self) -> bool:
        value = self.get("monitor_auto_scroll", DEFAULT_SETTINGS["monitor_auto_scroll"])
        return bool(value)

    @monitor_auto_scroll.setter
    def monitor_auto_scroll(self, value: bool) -> None:
        self.set("monitor_auto_scroll", bool(value))

    @property
    def monitor_timestamps(self) -> bool:
        value = self.get("monitor_timestamps", DEFAULT_SETTINGS["monitor_timestamps"])
        return bool(value)

    @monitor_timestamps.setter
    def monitor_timestamps(self, value: bool) -> None:
        self.set("monitor_timestamps", bool(value))
