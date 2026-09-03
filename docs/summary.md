# Espress View Summary

## Project Identity

`espress_view` is a CustomTkinter-based desktop GUI for ESP32-family serial discovery and firmware programming. The application wraps `esptool` while keeping device I/O and command execution off the Tk event thread.

## Implemented Architecture

- `main.py` owns the CustomTkinter window, device selection, partition state, flash control, progress state, and log view.
- PySerial enumerates operating-system serial ports, including Windows COM ports and Unix-style device nodes.
- A background device-scan thread sends `esptool read-mac` results to the Tk thread through an event queue.
- A separate flash worker starts `python -m esptool write_flash`, combines its output streams, and forwards output and progress events through the same queue.
- A lock protects the active subprocess so the circular Abort action can safely terminate the current operation.

## Interface Behavior

- Device Discovery lists verified ESP devices as `Chip Type | COM ID | MAC Address` and supports manual rescanning.
- Firmware Layout preserves one non-removable binary entry and supports up to four additional removable entries.
- Each firmware address initializes to `0x0000`, and the selected baud rate defaults to `115200`.
- The progress bar exposes `esptool` percentage updates and sits alongside the percentage text and Abort control.
- The log panel is collapsed by default; expanded mode provides clear and save actions without discarding console output when hidden.

## Operating Considerations

ESP programming requires a powered device, a compatible USB-to-UART driver, and bootloader access. The hardware reset and boot pins must allow `esptool` to establish its serial protocol handshake. A discovered serial port is only shown when the chip responds to the MAC-address command.

## Validation Performed

- Dependencies are installed in the project `.venv`.
- The GUI constructor, partition invariants, and log expand/collapse behavior have been checked using the selected Python interpreter.
- `main.py` passes Python bytecode compilation and has no editor diagnostics.
