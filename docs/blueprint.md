# Espress View Blueprint

## Purpose

`espress_view` is a developer-focused, cross-platform Python desktop application for discovering ESP devices and programming ESP32-family firmware over serial.

## Version 0.4.0

Version 0.4.0 includes the Monitor workspace, shared Device Discovery navigation, custom application and control icons, safe terminal interrupt shutdown, and packaged esptool support.

## Technology

- GUI: CustomTkinter.
- Serial discovery: PySerial enumerates candidate ports.
- ESP identification and programming: esptool runs in a child process.
- Background execution: Python threads and a queue keep Tk UI updates on the main thread.
- Application code: installable `src/espress_view` package with separate `core`, `flasher`, and `gui` modules.

## Application Structure

The `gui` package owns the CustomTkinter window, widgets, event queue, and user interactions. The `core` package owns serial-device discovery and serial-monitor I/O without depending on Tkinter. The `flasher` package validates firmware rows and manages the esptool child process. Icons are stored in the top-level `assets/icons` directory. The package `__main__.py` starts either the desktop application or the internal esptool worker. Run the installed application with `python -m espress_view`. See [architecture](architecture.md), [bootloader protocol notes](bootloader-protocols.md), [packaging](packaging-guide.md), and the [user manual](user-manual.md).

The shared `scripts/build.py` helper is application-agnostic and receives entry point, asset, executable, and metadata settings from its command line. See [scripts/README.md](../scripts/README.md) for integration and submodule usage.

## Device Discovery

Device discovery begins automatically at launch and runs again through `Rescan`.

For each visible serial port, the application starts a bounded `esptool read-mac` handshake. A responding ESP appears in the compact selector in this format:

```txt
Chip Type | COM ID | MAC Address
```

Non-ESP ports, unavailable ports, and ports that do not respond before the timeout are excluded. The selected COM ID becomes the `--port` argument used by the programming operation.

The Device Discovery selector is shared by the Monitor and Flash views. The sidebar switches only the lower workspace. Monitor is the default workspace at application startup.

## Serial Monitor

The Monitor workspace provides a dedicated baud-rate selector, defaulting to `115200`, and a Connect or Disconnect control. On connection, a background thread reads serial bytes and forwards decoded UTF-8 output to the monitor console.

The monitor console includes clear and save-log icon actions. The command field sends the entered text encoded as UTF-8 exactly as written. It does not add line-ending characters.

A monitor session must be disconnected before a flash operation starts. Likewise, the Monitor cannot connect while `esptool` is active.

When Flash targets the same COM ID currently connected to Monitor, the application shows a warning dialog. The user can select `Disconnect and Proceed` to close Monitor and start flashing or `Cancel` to preserve the active monitor session.

## Firmware Layout

Firmware Layout uses a dynamic partition list with these rules:

- The first row always exists, defaults to address `0x0000`, and cannot be removed.
- Additional rows also default to `0x0000`, show a red Remove button, and are renumbered after deletion.
- A row contains an index, binary-file input, Browse action, hexadecimal address input, and a fixed-width action slot.
- The application permits at most five rows.
- Baud-rate choices range from `9600` through `2000000`; the Flash default is `2000000`.

## Programming And Progress

Flash Program validates the selected device, binary paths, and hexadecimal addresses before starting an asynchronous command equivalent to:

```powershell
python -m espress_view --esptool-worker --chip auto --port COM_ID --baud BAUD_RATE write-flash ADDRESS BINARY
```

The application streams combined standard output and error into the retained log. Percentage values reported by `esptool` update the progress bar and its text label. The circular red Abort button remains disabled until the process begins and terminates the active process when selected.

## Log View

The log panel is collapsed by default, keeping the application window compact. The down-arrow expands the panel and the up-arrow collapses it. Expanded mode exposes clear and save-log icon actions; collapsing retains the log contents.
