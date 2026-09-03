#!/usr/bin/env python3
"""
     File: main.py
   Author: Project contributors
    Brief: Discover ESP devices and flash selected firmware partitions
  Created: 2026-09-03
    Updated: 2026-09-03
    Version: v0.2.0

Copyright: (c) 2026 Project contributors.

Description:
    Provides the CustomTkinter desktop interface and the background process
    management needed to discover serial devices and invoke esptool safely.
"""

import logging
import queue
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from serial.tools import list_ports

LOGGER = logging.getLogger(__name__)
MAX_PARTITIONS = 5
BAUD_RATES = (
    "9600", "14400", "19200", "28800", "38400", "57600", "74880", "76800", "115200", "128000", "153600",
    "230400", "256000", "460800", "512000", "576000", "921600", "1000000", "1500000", "2000000",
)


@dataclass
class Partition:
    """Store the widgets and values for one firmware partition."""

    row: ctk.CTkFrame
    index_label: ctk.CTkLabel
    file_path: ctk.StringVar
    address: ctk.StringVar
    action_slot: ctk.CTkFrame
    remove_button: ctk.CTkButton


class EspressView(ctk.CTk):
    """Provide serial discovery and asynchronous ESP firmware flashing."""

    def __init__(self) -> None:
        """Initialize the application window, controls, and event polling."""
        super().__init__()
        self.title("Espress View")
        self.geometry("1040x540")
        self.minsize(860, 540)
        self._active_process: subprocess.Popen[str] | None = None
        self._process_lock = threading.Lock()
        self._event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._partitions: list[Partition] = []
        self.port_var = ctk.StringVar(value="No device selected")
        self.baud_var = ctk.StringVar(value="115200")
        self.status_var = ctk.StringVar(value="Ready")
        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_text_var = ctk.StringVar(value="0%")
        self.log_visible = False
        self._build_interface()
        self.after(100, self._drain_events)
        self.after(200, self.scan_devices)

    def _build_interface(self) -> None:
        """Build the device, partition, and console areas."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        device_frame = ctk.CTkFrame(self)
        device_frame.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        device_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(device_frame, text="Device Discovery", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=14, pady=12
        )
        self.port_menu = ctk.CTkOptionMenu(
            device_frame,
            variable=self.port_var,
            values=["No device selected"],
        )
        self.port_menu.grid(row=0, column=1, sticky="ew", padx=10, pady=12)
        ctk.CTkButton(device_frame, text="Rescan", command=self.scan_devices, width=100).grid(
            row=0, column=2, padx=14, pady=12
        )

        workspace = ctk.CTkFrame(self)
        workspace.grid(row=1, column=0, sticky="ew", padx=18, pady=8)
        workspace.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(workspace, text="Firmware Layout", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=14, pady=(12, 6), sticky="w"
        )
        ctk.CTkLabel(workspace, text="Baud rate").grid(row=0, column=2, padx=(10, 4), pady=(12, 6))
        ctk.CTkOptionMenu(workspace, variable=self.baud_var, values=list(BAUD_RATES), width=110).grid(
            row=0, column=3, padx=(0, 14), pady=(12, 6)
        )
        self.partitions_frame = ctk.CTkFrame(workspace, fg_color="transparent")
        self.partitions_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=14, pady=6)
        self.partitions_frame.grid_columnconfigure(1, weight=1)
        self.partitions_frame.grid_columnconfigure(4, minsize=83)
        ctk.CTkButton(workspace, text="+ Add Partition", command=self.add_partition).grid(
            row=2, column=0, padx=14, pady=(6, 14), sticky="w"
        )
        self.add_partition()

        console_frame = ctk.CTkFrame(self)
        console_frame.grid(row=2, column=0, sticky="nsew", padx=18, pady=8)
        console_frame.grid_columnconfigure(0, weight=1)
        console_frame.grid_rowconfigure(3, weight=1)
        controls = ctk.CTkFrame(console_frame, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 12))
        controls.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(controls, text="Flash Program", command=self.flash_program).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(controls, textvariable=self.status_var).grid(row=0, column=2, padx=8, sticky="e")
        self.log_toggle = ctk.CTkButton(controls, text="v", command=self.toggle_log, width=28, height=28)
        self.log_toggle.grid(row=0, column=3, sticky="e")
        progress_controls = ctk.CTkFrame(console_frame, fg_color="transparent")
        progress_controls.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        progress_controls.grid_columnconfigure(0, weight=1)
        self.progress = ctk.CTkProgressBar(progress_controls, variable=self.progress_var, height=14)
        self.progress.grid(row=0, column=0, sticky="ew", pady=2)
        ctk.CTkLabel(progress_controls, textvariable=self.progress_text_var, width=44).grid(row=0, column=1, padx=(10, 6))
        self.abort_button = ctk.CTkButton(
            progress_controls,
            text="x",
            command=self.abort_flash,
            width=30,
            height=30,
            corner_radius=15,
            fg_color="#b53434",
            hover_color="#8e2727",
            state="disabled",
        )
        self.abort_button.grid(row=0, column=2, sticky="e")
        self.log_actions = ctk.CTkFrame(console_frame, fg_color="transparent")
        self.log_actions.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 6))
        self.log_actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(self.log_actions, text="⌫", command=self.clear_log, width=28, height=28).grid(row=0, column=1, padx=4)
        ctk.CTkButton(self.log_actions, text="↓", command=self.save_log, width=28, height=28).grid(row=0, column=2)
        self.console = ctk.CTkTextbox(console_frame, font=("Consolas", 12), wrap="word")
        self.console.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.console.configure(state="disabled")
        self.console.grid_remove()
        self.log_actions.grid_remove()

    def add_partition(self) -> None:
        """Append a partition configuration row up to the supported maximum."""
        if len(self._partitions) >= MAX_PARTITIONS:
            self._write_console(f"A maximum of {MAX_PARTITIONS} partitions is supported.\n")
            return
        row = ctk.CTkFrame(self.partitions_frame, fg_color="transparent")
        row.grid(row=len(self._partitions), column=0, columnspan=5, sticky="ew", pady=3)
        row.grid_columnconfigure(1, weight=1)
        file_path = ctk.StringVar()
        address = ctk.StringVar(value="0x0000")
        index_label = ctk.CTkLabel(row, text=f"{len(self._partitions) + 1}", width=24)
        index_label.grid(row=0, column=0, padx=(0, 6))
        ctk.CTkEntry(row, textvariable=file_path, placeholder_text="Firmware binary (.bin)").grid(
            row=0, column=1, sticky="ew", padx=4
        )
        action_slot = ctk.CTkFrame(row, width=75, height=28, fg_color="transparent")
        action_slot.grid(row=0, column=4, padx=(4, 0))
        action_slot.grid_propagate(False)
        remove_button = ctk.CTkButton(
            action_slot,
            text="Remove",
            width=75,
            fg_color="#b53434",
            hover_color="#8e2727",
        )
        partition = Partition(
            row=row,
            index_label=index_label,
            file_path=file_path,
            address=address,
            action_slot=action_slot,
            remove_button=remove_button,
        )
        ctk.CTkButton(row, text="Browse", width=80, command=lambda: self._choose_file(partition)).grid(row=0, column=2, padx=4)
        ctk.CTkEntry(row, textvariable=address, width=105, placeholder_text="0x1000").grid(row=0, column=3, padx=4)
        remove_button.configure(command=lambda: self.remove_partition(partition))
        remove_button.grid(row=0, column=0, sticky="nsew")
        self._partitions.append(partition)
        self._refresh_partition_controls()

    def remove_partition(self, partition: Partition) -> None:
        """Remove a non-baseline partition row and renumber the remaining rows."""
        if partition is self._partitions[0]:
            return
        partition.row.destroy()
        self._partitions.remove(partition)
        for index, current in enumerate(self._partitions):
            current.row.grid_configure(row=index)
            current.index_label.configure(text=str(index + 1))
        self._refresh_partition_controls()

    def _refresh_partition_controls(self) -> None:
        """Show removal controls only on partitions after the permanent first row."""
        for index, partition in enumerate(self._partitions):
            if index == 0:
                partition.remove_button.grid_remove()
            else:
                partition.remove_button.grid()

    def _choose_file(self, partition: Partition) -> None:
        """Open a file chooser and store the selected binary path."""
        selected = filedialog.askopenfilename(filetypes=[("Firmware binaries", "*.bin"), ("All files", "*.*")])
        if selected:
            partition.file_path.set(selected)

    def scan_devices(self) -> None:
        """Discover serial ports in a worker thread without blocking the interface."""
        self.status_var.set("Scanning devices...")
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        """Handshake each serial port and return ESP devices with their MAC addresses."""
        try:
            ports = list_ports.comports()
        except OSError as error:
            LOGGER.error("Serial device scan failed: %s", error)
            self._event_queue.put(("console", f"Device scan failed: {error}\n"))
            self._event_queue.put(("devices", ""))
            return
        devices = []
        for port in ports:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "esptool", "--port", port.device, "read-mac"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=6,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                LOGGER.info("ESP handshake skipped for %s: %s", port.device, error)
                continue
            mac_address = re.search(r"MAC:\s*((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})", result.stdout)
            chip_type = re.search(r"(?:Chip is|Detected chip type:)\s*(ESP[^\r\n]+)", result.stdout)
            if mac_address is not None:
                chip_name = chip_type.group(1).strip() if chip_type is not None else "ESP device"
                devices.append("\t".join((chip_name, port.device, mac_address.group(1).upper())))
        self._event_queue.put(("devices", "\n".join(devices)))

    def flash_program(self) -> None:
        """Validate the configuration and start the selected esptool operation."""
        port = self.port_var.get().split(" | ")[1] if " | " in self.port_var.get() else ""
        if not port:
            self._write_console("Select a serial device before flashing.\n")
            return
        arguments = ["--chip", "auto", "--port", port, "--baud", self.baud_var.get(), "write_flash"]
        for partition in self._partitions:
            binary = Path(partition.file_path.get())
            try:
                address = int(partition.address.get(), 0)
            except ValueError:
                self._write_console(f"Invalid flash address: {partition.address.get()}\n")
                return
            if not binary.is_file():
                self._write_console(f"Firmware file not found: {binary}\n")
                return
            arguments.extend([f"0x{address:x}", str(binary)])
        with self._process_lock:
            if self._active_process is not None:
                self._write_console("A flash operation is already running.\n")
                return
        self.status_var.set("Flashing...")
        self.progress_var.set(0)
        self.progress_text_var.set("0%")
        self.abort_button.configure(state="normal")
        self._write_console(f"$ {sys.executable} -m esptool {' '.join(arguments)}\n")
        threading.Thread(target=self._flash_worker, args=(arguments,), daemon=True).start()

    def _flash_worker(self, arguments: list[str]) -> None:
        """Run esptool, forwarding its combined output to the UI queue."""
        try:
            with self._process_lock:
                self._active_process = subprocess.Popen(
                    [sys.executable, "-m", "esptool", *arguments],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                process = self._active_process
            if process.stdout is not None:
                for line in process.stdout:
                    self._event_queue.put(("console", line))
                    percentage = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
                    if percentage is not None:
                        self._event_queue.put(("progress", percentage.group(1)))
            exit_code = process.wait()
            self._event_queue.put(("complete", str(exit_code)))
        except OSError as error:
            LOGGER.error("Could not start esptool: %s", error)
            self._event_queue.put(("console", f"Unable to start esptool: {error}\n"))
            self._event_queue.put(("complete", "startup-error"))
        finally:
            with self._process_lock:
                self._active_process = None

    def abort_flash(self) -> None:
        """Terminate the active esptool process, if a flash is underway."""
        with self._process_lock:
            process = self._active_process
        if process is None or process.poll() is not None:
            self._write_console("No active flash operation to abort.\n")
            self.abort_button.configure(state="disabled")
            return
        process.terminate()
        self.status_var.set("Aborting...")
        self.abort_button.configure(state="disabled")
        self._write_console("Abort requested.\n")

    def toggle_log(self) -> None:
        """Toggle the retained log panel and update its directional control."""
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.grid_rowconfigure(2, weight=1)
            self.geometry("1040x720")
            self.log_actions.grid()
            self.console.grid()
            self.log_toggle.configure(text="^")
        else:
            self.grid_rowconfigure(2, weight=0)
            self.geometry("1040x540")
            self.log_actions.grid_remove()
            self.console.grid_remove()
            self.log_toggle.configure(text="v")

    def clear_log(self) -> None:
        """Remove all retained output from the expanded console."""
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")

    def save_log(self) -> None:
        """Save retained console output to a user-selected text file."""
        destination = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not destination:
            return
        try:
            Path(destination).write_text(self.console.get("1.0", "end-1c"), encoding="utf-8")
        except OSError as error:
            LOGGER.error("Could not save log: %s", error)
            self._write_console(f"Could not save log: {error}\n")
            return
        self._write_console(f"Log saved: {destination}\n")

    def _drain_events(self) -> None:
        """Apply worker results on the UI thread and schedule the next poll."""
        while True:
            try:
                event, value = self._event_queue.get_nowait()
            except queue.Empty:
                break
            if event == "console":
                self._write_console(value)
            elif event == "devices":
                devices = [device.split("\t") for device in value.splitlines()]
                self._display_devices(devices)
                self.status_var.set(f"Found {len(devices)} serial device(s)")
                self._write_console(f"Scan complete: {len(devices)} serial device(s) found.\n")
            elif event == "complete":
                self.status_var.set("Ready" if value == "0" else f"Flash ended ({value})")
                self.abort_button.configure(state="disabled")
                self._write_console(f"esptool completed with status: {value}\n")
            elif event == "progress":
                percentage = min(float(value), 100)
                self.progress_var.set(percentage / 100)
                self.progress_text_var.set(f"{percentage:.0f}%")
        self.after(100, self._drain_events)

    def _display_devices(self, devices: list[list[str]]) -> None:
        """Populate compact device entries containing chip type, COM ID, and MAC."""
        entries = [f"{chip_type} | {port} | {mac_address}" for chip_type, port, mac_address in devices]
        self.port_menu.configure(values=entries or ["No device selected"])
        self.port_var.set(entries[0] if entries else "No device selected")

    def _write_console(self, message: str) -> None:
        """Append text to the read-only console and reveal its latest output."""
        self.console.configure(state="normal")
        self.console.insert("end", message)
        self.console.see("end")
        self.console.configure(state="disabled")


def main() -> None:
    """Configure logging and run the Espress View application."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    application = EspressView()
    application.mainloop()


if __name__ == "__main__":
    main()