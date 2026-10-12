# Architecture

Espress View is a local desktop application. The CustomTkinter frontend coordinates UI state and delegates device access and firmware flashing to backend modules. It does not run a network server.

## Layers

| Layer | Responsibility | Boundary |
|---|---|---|
| `gui` | Main window, discovery selector, Monitor and Flash workspaces, progress/log rendering, user interactions | Owns all Tk/CustomTkinter widgets and variables |
| `core` | Enumerate serial ports, handshake candidate ESP devices, open/read/write/close the serial monitor | No Tkinter or CustomTkinter imports |
| `flasher` | Validate addresses and binaries, build esptool arguments, run/abort the esptool child process, stream output | No Tkinter or CustomTkinter imports |
| `utils` | Resolve icons in source/PyInstaller execution; guard against duplicate Windows launches | Platform/resource helpers |
| `assets/icons` | Application and control images | Shared runtime resources |

The package entry point is `espress_view.__main__`. In a source checkout, use `python -m espress_view`; PyInstaller packages the same entry point for executable distribution.

```mermaid
flowchart TB
    User[User]
    subgraph App[Espress View process]
        Entry[__main__.py]
        GUI[gui.app<br/>CustomTkinter]
        Core[core<br/>Discovery and Monitor]
        Flasher[flasher<br/>Validation and Runner]
        Queue[queue.Queue]
        Entry --> GUI
        GUI --> Core
        GUI --> Flasher
        Core -. discovery/monitor results .-> Queue
        Flasher -. output/progress/completion .-> Queue
        Queue --> GUI
    end
    OS[Operating system serial ports]
    Device[ESP device]
    Worker[espress_view worker process<br/>esptool]
    Core --> OS
    Core --> Device
    Core --> Worker
    Flasher --> Worker
    User --> GUI
```

## Thread and queue boundary

The GUI starts device discovery and serial reading on background threads so serial waits do not block the window. The flash thread manages a child worker process and forwards its merged output and parsed percentage updates. These workers publish `(event, value)` pairs into a thread-safe `queue.Queue`. They must not call Tk methods or mutate Tk variables.

The UI schedules `_drain_events` with `after(100, ...)`, drains available queue entries on the Tk thread, updates widgets, then schedules the next poll. Monitor writes are issued in response to UI actions; monitor disconnect closes the active serial handle and sets the worker stop event.

```mermaid
sequenceDiagram
    participant UI as CTk UI thread
    participant Worker as Discovery/Monitor/Flash worker
    participant Q as queue.Queue
    participant Timer as CTk.after()
    UI->>Timer: schedule _drain_events()
    Timer-->>UI: invoke callback on UI thread
    UI->>Q: get_nowait() until queue is empty
    Worker->>Worker: perform serial I/O or read esptool output
    Worker->>Q: put((event, value))
    UI->>Q: get_nowait()
    Q-->>UI: event and value
    UI->>UI: update widgets and Tk variables
    UI->>Timer: schedule next poll
```

## Discovery flow

At startup and on Rescan, the GUI starts a scan worker. `core.device_discovery` enumerates ports through PySerial, invokes the bundled esptool worker with `read-mac` per candidate (six-second timeout), and returns devices that produced a MAC address. The GUI displays `Chip Type | COM ID | MAC Address`.

## Flash flow

The GUI passes selected port, baud rate, and firmware rows to `flasher.arguments`. After local validation, a background thread calls `flasher.runner.FlashRunner`, which starts the worker process with combined stdout/stderr. Output and completion events go to the UI queue; percentage text is parsed from esptool output. Abort requests termination of the active child process.

The application does not implement ESP bootloader framing or erase/write/verify commands itself; the bundled esptool performs those chip-specific operations.
