# Espress View

Desktop utility for discovering ESP serial devices and programming one to five firmware binaries with `esptool`.

## Features

- ESP discovery that verifies each serial port through `esptool read-mac` and displays `Chip Type | COM ID | MAC Address`.
- Firmware Layout with one permanent first binary row and up to four removable additional partition rows.
- Configurable serial baud rates from `9600` to `2000000`, with `115200` selected by default.
- Background firmware programming with streamed `esptool` output, a percentage progress bar, and an enabled-only-while-flashing Abort control.
- Collapsible log view with clear and save-log controls when expanded.

## Setup

Create and activate a virtual environment from PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

On macOS or Linux, activate it with `source .venv/bin/activate` before installing dependencies and running the app.

## Firmware Programming

1. Connect and power the ESP device. It must be able to enter its ROM bootloader.
2. Select the device from Device Discovery. The selector entry contains its chip type, serial port, and MAC address.
3. In Firmware Layout, choose the binary for the permanent first row and enter its target address. Every row defaults to `0x0000`.
4. Add up to four more partitions as needed. Added rows can be removed; the first row cannot.
5. Select the baud rate and choose `Flash Program`.

The app runs `python -m esptool --chip auto --port COM_ID --baud BAUD_RATE write_flash` in a background thread. The circular Abort button is unavailable until this command starts and requests process termination when selected.

## Logs

The log panel starts collapsed to keep the main window compact. Select the down-arrow control to expand it and the up-arrow control to collapse it.

When expanded, the log toolbar provides these icon controls:

- `⌫` clears the current console output.
- `↓` saves the current console output to a `.log` or `.txt` file.

## Device Discovery

The initial device scan runs a short `esptool read-mac` handshake on every visible serial port. Only responding ESP devices appear in the selector, identified by their serial port and MAC address. A device must be powered, connected, and able to enter its ROM bootloader for the handshake to succeed.

Use `Rescan` after connecting, disconnecting, or resetting a device.

## Project Files

```txt
espress_view/
├── main.py             # CustomTkinter application
├── requirements.txt    # Runtime dependencies
├── README.md           # Installation and use guide
├── blueprint.md        # Current application specification
└── summary.md          # Technical and implementation summary
```
