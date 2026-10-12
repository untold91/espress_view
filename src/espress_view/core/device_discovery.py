"""Discover and identify connected ESP serial devices."""

import logging
import re
import subprocess
from dataclasses import dataclass

from serial.tools import list_ports

from espress_view.flasher.runner import esptool_worker_command

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EspDevice:
    """Describe an ESP device that responded to the esptool handshake."""

    chip_type: str
    port: str
    mac_address: str


def discover_devices(timeout: float = 6) -> list[EspDevice]:
    """Handshake with visible serial ports and return responsive ESP devices."""
    devices: list[EspDevice] = []
    for port in list_ports.comports():
        try:
            result = subprocess.run(
                esptool_worker_command(["--port", port.device, "read-mac"]),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            LOGGER.info("ESP handshake skipped for %s: %s", port.device, error)
            continue
        mac_address = re.search(r"MAC:\s*((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})", result.stdout)
        if mac_address is None:
            continue
        chip_type = re.search(r"(?:Chip is|Detected chip type:)\s*(ESP[^\r\n]+)", result.stdout)
        chip_name = chip_type.group(1).strip() if chip_type is not None else "ESP device"
        devices.append(EspDevice(chip_name, port.device, mac_address.group(1).upper()))
    return devices
