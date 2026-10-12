"""Tests for the application backend services."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from espress_view.core import serial_monitor
from espress_view.core import device_discovery
from espress_view.flasher.arguments import build_flash_arguments
from espress_view.flasher.runner import FlashRunner, esptool_worker_command
from espress_view.utils.paths import resource_path


class FlashingTests(unittest.TestCase):
    def test_builds_arguments_for_existing_firmware(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".bin") as firmware:
            self.assertEqual(
                build_flash_arguments("COM7", "2000000", [(firmware.name, "0x1000")]),
                [
                    "--chip",
                    "auto",
                    "--port",
                    "COM7",
                    "--baud",
                    "2000000",
                    "write-flash",
                    "0x1000",
                    firmware.name,
                ],
            )

    def test_rejects_invalid_addresses(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid flash address"):
            build_flash_arguments("COM7", "2000000", [("firmware.bin", "not-hex")])

    def test_rejects_missing_firmware(self) -> None:
        with self.assertRaisesRegex(ValueError, "Firmware file not found"):
            build_flash_arguments("COM7", "2000000", [("missing-firmware.bin", "0x1000")])


class FlashRunnerTests(unittest.TestCase):
    @patch("espress_view.flasher.runner.subprocess.Popen")
    def test_notifies_when_the_child_process_is_started(self, popen: Mock) -> None:
        process = Mock()
        process.stdout = iter(["50%\n"])
        process.wait.return_value = 0
        popen.return_value = process
        started = Mock()
        output: list[str] = []
        runner = FlashRunner()

        self.assertEqual(runner.run(["--port", "COM7"], output.append, started), 0)

        started.assert_called_once_with()
        self.assertEqual(output, ["50%\n"])
        self.assertFalse(runner.is_running)


class DeviceDiscoveryTests(unittest.TestCase):
    @patch.object(
        device_discovery.subprocess,
        "run",
        side_effect=[
            SimpleNamespace(stdout="Chip is ESP32-D0WD-V3\nMAC: aa:bb:cc:dd:ee:ff\n"),
            SimpleNamespace(stdout="No ESP response"),
        ],
    )
    @patch.object(
        device_discovery.list_ports,
        "comports",
        return_value=[SimpleNamespace(device="COM7"), SimpleNamespace(device="COM8")],
    )
    def test_returns_only_responding_esp_devices(self, _ports: Mock, _run: Mock) -> None:
        self.assertEqual(
            device_discovery.discover_devices(),
            [device_discovery.EspDevice("ESP32-D0WD-V3", "COM7", "AA:BB:CC:DD:EE:FF")],
        )


class SerialMonitorTests(unittest.TestCase):
    def test_sends_exact_utf8_text_without_line_endings(self) -> None:
        connection = SimpleNamespace(write=Mock())
        serial_monitor.send(connection, "hello")
        connection.write.assert_called_once_with(b"hello")

    def test_worker_runs_the_package_entry_point(self) -> None:
        self.assertEqual(
            esptool_worker_command(["--port", "COM7"]),
            [
                sys.executable,
                "-m",
                "espress_view",
                "--esptool-worker",
                "--port",
                "COM7",
            ],
        )

    def test_application_icons_resolve_from_the_assets_directory(self) -> None:
        self.assertTrue(resource_path("icons", "exe-file.ico").is_file())

    def test_frozen_icons_resolve_from_the_bundle_directory(self) -> None:
        with tempfile.TemporaryDirectory() as bundle_directory:
            icon = Path(bundle_directory) / "assets" / "icons" / "exe-file.ico"
            icon.parent.mkdir(parents=True)
            icon.touch()
            with patch.object(sys, "_MEIPASS", bundle_directory, create=True):
                self.assertEqual(resource_path("icons", "exe-file.ico"), icon)


if __name__ == "__main__":
    unittest.main()
