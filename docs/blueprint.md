# Espress View Blueprint

## Purpose

`espress_view` is a developer-focused, cross-platform Python desktop application for discovering ESP devices and programming ESP32-family firmware over serial.

## Technology

- GUI: CustomTkinter.
- Serial discovery: PySerial enumerates candidate ports.
- ESP identification and programming: `python -m esptool`.
- Background execution: Python threads and a queue keep Tk UI updates on the main thread.

## Device Discovery

Device discovery begins automatically at launch and runs again through `Rescan`.

For each visible serial port, the application starts a bounded `esptool read-mac` handshake. A responding ESP appears in the compact selector in this format:

```txt
Chip Type | COM ID | MAC Address
```

Non-ESP ports, unavailable ports, and ports that do not respond before the timeout are excluded. The selected COM ID becomes the `--port` argument used by the programming operation.

## Firmware Layout

Firmware Layout uses a dynamic partition list with these rules:

- The first row always exists, defaults to address `0x0000`, and cannot be removed.
- Additional rows also default to `0x0000`, show a red Remove button, and are renumbered after deletion.
- A row contains an index, binary-file input, Browse action, hexadecimal address input, and a fixed-width action slot.
- The application permits at most five rows.
- Baud-rate choices range from `9600` through `2000000`; the default is `115200`.

## Programming And Progress

Flash Program validates the selected device, binary paths, and hexadecimal addresses before starting an asynchronous command equivalent to:

```powershell
python -m esptool --chip auto --port COM_ID --baud BAUD_RATE write_flash ADDRESS BINARY
```

The application streams combined standard output and error into the retained log. Percentage values reported by `esptool` update the progress bar and its text label. The circular red Abort button remains disabled until the process begins and terminates the active process when selected.

## Log View

The log panel is collapsed by default, keeping the application window compact. The down-arrow expands the panel and the up-arrow collapses it. Expanded mode exposes clear and save-log icon actions; collapsing retains the log contents.
