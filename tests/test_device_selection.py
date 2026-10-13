"""Tests for device selection safety, connection protection, and scan behavior."""

# Test names are descriptive, and GUI tests intentionally inspect widget internals.
# pylint: disable=duplicate-code,missing-class-docstring,missing-function-docstring,protected-access,wrong-import-position

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from espress_view.gui.app import EspressView


class DeviceSelectionSafetyTests(unittest.TestCase):
    @staticmethod
    def _subject() -> Mock:
        subject = Mock()
        subject.port_var = Mock()
        subject.port_menu = Mock()
        subject.device_status_var = Mock()
        subject.device_status_label = Mock()
        subject.scan_button = Mock()
        subject.flash_button = Mock()
        subject.monitor_connect_button = Mock()
        subject.monitor_baud_menu = Mock()
        subject.baud_menu = Mock()
        subject._monitor_serial = None
        subject._flash_busy = False
        subject._scan_active = False
        subject._initial_scan = False
        return subject

    def test_preserves_selected_port_across_rescans(self) -> None:
        subject = self._subject()
        subject._selected_port.return_value = "COM4"

        devices = [
            ["ESP32", "COM3", "AA:BB:CC:DD:EE:01"],
            ["ESP32-S3", "COM4", "AA:BB:CC:DD:EE:02"],
        ]
        EspressView._display_devices(subject, devices)

        subject.port_var.set.assert_called_once_with("ESP32-S3 | COM4 | AA:BB:CC:DD:EE:02")

    def test_preserves_selected_port_when_order_changes(self) -> None:
        subject = self._subject()
        subject._selected_port.return_value = "COM4"

        # Re-ordered list of devices
        devices = [
            ["ESP32-S3", "COM4", "AA:BB:CC:DD:EE:02"],
            ["ESP32", "COM3", "AA:BB:CC:DD:EE:01"],
        ]
        EspressView._display_devices(subject, devices)

        subject.port_var.set.assert_called_once_with("ESP32-S3 | COM4 | AA:BB:CC:DD:EE:02")

    def test_clears_selection_and_warns_when_selected_port_disappears(self) -> None:
        subject = self._subject()
        subject._selected_port.return_value = "COM4"

        devices = [
            ["ESP32", "COM3", "AA:BB:CC:DD:EE:01"],
        ]
        EspressView._display_devices(subject, devices)

        subject.port_var.set.assert_called_once_with("No device selected")
        subject.device_status_var.set.assert_called_once_with("Selected port COM4 disconnected")
        subject.device_status_label.configure.assert_called_once()

    def test_empty_discovery_result_clears_selection(self) -> None:
        subject = self._subject()
        subject._selected_port.return_value = "COM4"

        EspressView._display_devices(subject, [])

        subject.port_menu.configure.assert_called_once_with(values=["No device selected"])
        subject.port_var.set.assert_called_once_with("No device selected")

    def test_repeated_scan_without_previous_selection_does_not_select_first_device(self) -> None:
        subject = self._subject()
        subject._selected_port.return_value = ""
        subject._initial_scan = False

        devices = [
            ["ESP32", "COM3", "AA:BB:CC:DD:EE:01"],
            ["ESP32-S3", "COM4", "AA:BB:CC:DD:EE:02"],
        ]
        EspressView._display_devices(subject, devices)

        subject.port_var.set.assert_called_once_with("No device selected")

    def test_initial_scan_selects_first_device_if_available(self) -> None:
        subject = self._subject()
        subject._selected_port.return_value = ""
        subject._initial_scan = True

        devices = [
            ["ESP32", "COM3", "AA:BB:CC:DD:EE:01"],
            ["ESP32-S3", "COM4", "AA:BB:CC:DD:EE:02"],
        ]
        EspressView._display_devices(subject, devices)

        subject.port_var.set.assert_called_once_with("ESP32 | COM3 | AA:BB:CC:DD:EE:01")

    def test_rescan_rejected_when_monitor_is_connected(self) -> None:
        subject = self._subject()
        subject._monitor_serial = Mock()
        subject._closing = False
        subject._write_monitor_log = Mock()

        EspressView.scan_devices(subject)

        subject._write_monitor_log.assert_called_once()
        subject.device_status_var.set.assert_called_once_with("Disconnect Monitor to rescan")

    def test_controls_locked_while_monitor_connected(self) -> None:
        subject = self._subject()
        subject._monitor_serial = Mock()
        subject._flash_busy = False

        EspressView._set_scan_controls(subject, scanning=False)

        subject.port_menu.configure.assert_called_with(state="disabled")
        subject.scan_button.configure.assert_called_with(state="disabled")
        subject.monitor_baud_menu.configure.assert_called_with(state="disabled")

    def test_controls_restored_after_monitor_disconnected(self) -> None:
        subject = self._subject()
        subject._monitor_serial = None
        subject._flash_busy = False

        EspressView._set_scan_controls(subject, scanning=False)

        subject.port_menu.configure.assert_called_with(state="normal")
        subject.scan_button.configure.assert_called_with(state="normal")
        subject.monitor_baud_menu.configure.assert_called_with(state="normal")

    def test_controls_locked_while_flashing(self) -> None:
        subject = self._subject()
        subject._monitor_serial = None
        subject._flash_busy = True

        EspressView._set_scan_controls(subject, scanning=False)

        subject.port_menu.configure.assert_called_with(state="disabled")
        subject.scan_button.configure.assert_called_with(state="disabled")
        subject.flash_button.configure.assert_called_with(state="disabled")
        subject.monitor_connect_button.configure.assert_called_with(state="disabled")


if __name__ == "__main__":
    unittest.main()
