# Espress View Summary

## Project Identity

`espress_view` is a CustomTkinter-based desktop GUI for ESP32-family serial discovery, serial monitoring, and firmware programming. A shared Device Discovery selector feeds the lower Monitor and Flash workspaces.

## Version 0.4.0

This release includes serial monitoring, shared navigation, icon-based controls and tooltips, a safer terminal shutdown path, packaged esptool support, and the `2000000` Flash baud-rate default.

## Implemented Architecture

- `src/espress_view/gui/app.py` owns the CustomTkinter window, device selection, partition state, flash controls, progress state, and log views.
- `src/espress_view/core/device_discovery.py` performs serial-port enumeration and esptool handshakes.
- `src/espress_view/core/serial_monitor.py` opens, reads, and writes the selected monitor port.
- `src/espress_view/flasher/arguments.py` validates firmware rows and constructs esptool arguments.
- `src/espress_view/flasher/runner.py` runs and stops the esptool child process.
- `src/espress_view/__main__.py` is the package entry point and handles the internal worker mode.
- `scripts/build.py` is a generic PyInstaller helper; the project supplies entry point, resources, name, and optional version metadata as CLI options.
- `tests/test_services.py` verifies firmware validation, ESP discovery filtering, serial-text behavior, and the package worker command.
- PySerial enumerates operating-system serial ports, including Windows COM ports and Unix-style device nodes.
- Background device-scan and serial-monitor threads deliver results to Tk through an event queue.
- The flash runner combines esptool output streams, forwards progress, and protects the active subprocess while it is aborted or closed.
- `assets/icons` stores the application and control icons outside the Python source package.
- `pyproject.toml` configures setuptools to package the `src` layout and install runtime icons.

## Interface Behavior

- Device Discovery lists verified ESP devices as `Chip Type | COM ID | MAC Address` and supports manual rescanning.
- Monitor is the default lower workspace; Flash is selected through the sidebar when required.
- Firmware Layout preserves one non-removable binary entry and supports up to four additional removable entries.
- Each firmware address initializes to `0x0000`; Flash defaults to `2000000` baud and Monitor defaults to `115200` baud.
- The progress bar exposes `esptool` percentage updates and sits alongside the percentage text and Abort control.
- The log panel is collapsed by default; expanded mode provides clear and save actions without discarding console output when hidden.
- Monitor provides Connect and Disconnect controls, clear and save actions, and a command field that sends exact UTF-8 text without appending line endings.
- Attempting to flash the device currently connected to Monitor presents a Disconnect and Proceed or Cancel decision.

## Operating Considerations

ESP programming requires a powered device, a compatible USB-to-UART driver, and bootloader access. The hardware reset and boot pins must allow `esptool` to establish its serial protocol handshake. A discovered serial port is only shown when the chip responds to the MAC-address command.

## Validation Performed

- Eight backend unit tests pass.
- The frontend imports with application icons resolved from the top-level assets directory.
- The configured generic PyInstaller command produces a one-file executable whose bundled esptool worker starts successfully.
