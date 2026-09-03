#!/usr/bin/env python3
"""
     File: main.py
   Author: Project contributors
    Brief: Discover ESP devices and flash selected firmware partitions
  Created: 2026-09-03
    Updated: 2026-09-03
    Version: v0.4.0

Copyright: (c) 2026 Project contributors.

Description:
    Provides the CustomTkinter desktop interface and the background process
    management needed to discover serial devices and invoke esptool safely.
"""

import ctypes
import logging
import queue
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import TclError, filedialog

import customtkinter as ctk
import esptool
import serial
from PIL import Image, ImageTk
from esptool.util import FatalError
from serial.tools import list_ports

LOGGER = logging.getLogger(__name__)
SINGLE_INSTANCE_MUTEX = "Local\\EspressViewSingleInstance"
ERROR_ALREADY_EXISTS = 183
MAX_PARTITIONS = 5
BAUD_RATES = (
    "9600", "14400", "19200", "28800", "38400", "57600", "74880", "76800", "115200", "128000", "153600",
    "230400", "256000", "460800", "512000", "576000", "921600", "1000000", "1500000", "2000000",
)

_instance_state = {"handle": None}


def acquire_single_instance() -> bool:
    """Acquire the process-wide Windows mutex used to prevent duplicate launches."""
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    mutex_handle = kernel32.CreateMutexW(None, True, SINGLE_INSTANCE_MUTEX)
    if not mutex_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(mutex_handle)
        return False
    _instance_state["handle"] = int(mutex_handle)
    return True


def release_single_instance() -> None:
    """Release the Windows mutex held by this application process."""
    mutex_handle = _instance_state["handle"]
    if mutex_handle is None or sys.platform != "win32":
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle(ctypes.c_void_p(mutex_handle))
    _instance_state["handle"] = None


def esptool_worker_command(arguments: list[str]) -> list[str]:
    """Build a command that runs the bundled esptool worker in any launch mode."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--esptool-worker", *arguments]
    return [sys.executable, str(Path(__file__).resolve()), "--esptool-worker", *arguments]


def run_esptool_worker(arguments: list[str]) -> int:
    """Run esptool inside the current Python or packaged executable process."""
    try:
        esptool.main(arguments)
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 1
    except FatalError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


@dataclass
class Partition:
    """Store the widgets and values for one firmware partition."""

    row: ctk.CTkFrame
    index_label: ctk.CTkLabel
    file_path: ctk.StringVar
    address: ctk.StringVar
    action_slot: ctk.CTkFrame
    remove_button: ctk.CTkButton


class Tooltip:
    """Display a short hover label for a CustomTkinter widget."""

    def __init__(self, widget: ctk.CTkBaseClass, text: str) -> None:
        """Bind the tooltip text to the target widget's hover events."""
        self.widget = widget
        self.text = text
        self.window: ctk.CTkToplevel | None = None
        self._show_job: str | None = None
        self.widget.bind("<Enter>", self.schedule_show, add="+")
        self.widget.bind("<Leave>", self.hide, add="+")
        self.widget.bind("<ButtonPress>", self.hide, add="+")
        self.widget.bind("<FocusOut>", self.hide, add="+")
        self.widget.bind("<Unmap>", self.hide, add="+")
        self.widget.bind("<Destroy>", self.hide, add="+")

    def schedule_show(self, _event: object | None = None) -> None:
        """Delay tooltip creation until the pointer remains on a visible control."""
        if self._show_job is None:
            self._show_job = self.widget.after(500, self.show)

    def show(self) -> None:
        """Create and position a tooltip if its target is still visible."""
        self._show_job = None
        if self.window is not None or not self.widget.winfo_ismapped():
            return
        if self.window is not None:
            return
        try:
            self.window = ctk.CTkToplevel(self.widget)
            self.window.overrideredirect(True)
            self.window.transient(self.widget.winfo_toplevel())
            x_position = self.widget.winfo_pointerx() + 12
            y_position = self.widget.winfo_pointery() + 12
            self.window.geometry(f"+{x_position}+{y_position}")
            ctk.CTkLabel(self.window, text=self.text, corner_radius=4).pack(padx=1, pady=1)
        except TclError:
            self.window = None

    def hide(self, _event: object | None = None) -> None:
        """Cancel pending display and destroy any visible tooltip window."""
        if self._show_job is not None:
            try:
                self.widget.after_cancel(self._show_job)
            except TclError:
                pass
            self._show_job = None
        if self.window is not None:
            try:
                self.window.destroy()
            except TclError:
                pass
            self.window = None


class EspressView(ctk.CTk):
    """Provide shared ESP discovery, serial monitoring, and firmware flashing."""

    def __init__(self) -> None:
        """Initialize the application window, controls, and event polling."""
        super().__init__()
        self.title("Espress View")
        self.geometry("1040x540")
        self.minsize(860, 540)
        self._application_icon = ImageTk.PhotoImage(Image.open(Path(__file__).parent / "icons" / "exe-file.ico"))
        self.iconphoto(True, self._application_icon)
        self._active_process: subprocess.Popen[str] | None = None
        self._process_lock = threading.Lock()
        self._event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._partitions: list[Partition] = []
        self._monitor_serial: serial.Serial | None = None
        self._monitor_port: str | None = None
        self._monitor_thread: threading.Thread | None = None
        self._monitor_stop = threading.Event()
        self.monitor_view: ctk.CTkFrame
        self.monitor_connect_button: ctk.CTkButton
        self.monitor_console: ctk.CTkTextbox
        self.monitor_send_button: ctk.CTkButton
        self.port_var = ctk.StringVar(value="No device selected")
        self.baud_var = ctk.StringVar(value="2000000")
        self.monitor_baud_var = ctk.StringVar(value="115200")
        self.monitor_input_var = ctk.StringVar()
        self.monitor_status_var = ctk.StringVar(value="Disconnected")
        self.status_var = ctk.StringVar(value="Ready")
        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_text_var = ctk.StringVar(value="0%")
        self.log_visible = False
        self._icons = self._load_icons()
        self._build_interface()
        self.protocol("WM_DELETE_WINDOW", self.close_application)
        self.after(100, self._drain_events)
        self.after(200, self.scan_devices)

    @staticmethod
    def _add_tooltip(widget: ctk.CTkBaseClass, text: str) -> None:
        """Attach a concise hover tooltip to an icon-only control."""
        Tooltip(widget, text)

    def _load_icons(self) -> dict[str, ctk.CTkImage]:
        """Load white control icons while retaining the original image alpha masks."""
        icon_directory = Path(__file__).parent / "icons"
        icon_sizes = {
            "abort": (16, 16),
            "clear": (16, 16),
            "expand": (16, 16),
            "flash": (18, 18),
            "minimize": (16, 16),
            "monitor": (18, 18),
            "save": (16, 16),
        }
        icon_files = {
            "abort": "cancel",
            "clear": "backspace",
            "expand": "expand-arrows",
            "flash": "lightning",
            "minimize": "minimize",
            "monitor": "computer",
            "save": "inbox",
        }
        icons = {}
        for name, filename in icon_files.items():
            source = Image.open(icon_directory / f"{filename}.png").convert("RGBA")
            white_icon = Image.new("RGBA", source.size, "white")
            white_icon.putalpha(source.getchannel("A"))
            icons[name] = ctk.CTkImage(light_image=white_icon, dark_image=white_icon, size=icon_sizes[name])
        return icons

    def _build_interface(self) -> None:
        """Build the device, partition, and console areas."""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        navigation = ctk.CTkFrame(self, width=132)
        navigation.grid(row=0, column=0, sticky="ns", padx=(18, 8), pady=18)
        navigation.grid_propagate(False)
        self.monitor_nav = ctk.CTkButton(
            navigation,
            text="Monitor",
            image=self._icons["monitor"],
            compound="left",
            command=self.show_monitor,
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
        )
        self.monitor_nav.pack(fill="x", padx=10, pady=4)
        self.flash_nav = ctk.CTkButton(
            navigation,
            text="Flash",
            image=self._icons["flash"],
            compound="left",
            command=self.show_flash,
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
        )
        self.flash_nav.pack(fill="x", padx=10, pady=4)

        main_area = ctk.CTkFrame(self, fg_color="transparent")
        main_area.grid(row=0, column=1, sticky="nsew", padx=(0, 18), pady=18)
        main_area.grid_columnconfigure(0, weight=1)
        main_area.grid_rowconfigure(1, weight=1)

        device_frame = ctk.CTkFrame(main_area)
        device_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
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

        self.view_area = ctk.CTkFrame(main_area, fg_color="transparent")
        self.view_area.grid(row=1, column=0, sticky="nsew")
        self.view_area.grid_columnconfigure(0, weight=1)
        self.view_area.grid_rowconfigure(0, weight=1)
        self.flash_view = ctk.CTkFrame(self.view_area, fg_color="transparent")
        self.flash_view.grid(row=0, column=0, sticky="nsew")
        self.flash_view.grid_columnconfigure(0, weight=1)
        self.flash_view.grid_rowconfigure(1, weight=1)

        workspace = ctk.CTkFrame(self.flash_view)
        workspace.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        workspace.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(workspace, text="Firmware Layout", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=14, pady=(12, 6), sticky="w"
        )
        ctk.CTkLabel(workspace, text="Buad Rate").grid(row=0, column=2, padx=(10, 4), pady=(12, 6))
        ctk.CTkOptionMenu(workspace, variable=self.baud_var, values=list(BAUD_RATES), width=110).grid(
            row=0, column=3, padx=(0, 14), pady=(12, 6)
        )
        self.partitions_frame = ctk.CTkFrame(workspace, fg_color="transparent")
        self.partitions_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=14, pady=6)
        self.partitions_frame.grid_columnconfigure(1, weight=1)
        self.partitions_frame.grid_columnconfigure(4, minsize=38)
        ctk.CTkButton(workspace, text="+ Add Partition", command=self.add_partition).grid(
            row=2, column=0, padx=14, pady=(6, 14), sticky="w"
        )
        self.add_partition()

        console_frame = ctk.CTkFrame(self.flash_view)
        console_frame.grid(row=1, column=0, sticky="nsew")
        console_frame.grid_columnconfigure(0, weight=1)
        console_frame.grid_rowconfigure(3, weight=1)
        controls = ctk.CTkFrame(console_frame, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 12))
        controls.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(controls, text="Flash Program", command=self.flash_program).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(controls, textvariable=self.status_var).grid(row=0, column=2, padx=8, sticky="e")
        self.log_toggle = ctk.CTkButton(
            controls,
            text="",
            image=self._icons["expand"],
            command=self.toggle_log,
            width=30,
            height=30,
            corner_radius=6,
        )
        self.log_toggle.grid(row=0, column=3, sticky="e")
        self.log_tooltip = Tooltip(self.log_toggle, "Maximize logs")
        progress_controls = ctk.CTkFrame(console_frame, fg_color="transparent")
        progress_controls.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        progress_controls.grid_columnconfigure(0, weight=1)
        self.progress = ctk.CTkProgressBar(progress_controls, variable=self.progress_var, height=14)
        self.progress.grid(row=0, column=0, sticky="ew", pady=2)
        ctk.CTkLabel(progress_controls, textvariable=self.progress_text_var, width=44).grid(row=0, column=1, padx=(10, 6))
        self.abort_button = ctk.CTkButton(
            progress_controls,
            text="",
            image=self._icons["abort"],
            command=self.abort_flash,
            width=30,
            height=30,
            corner_radius=6,
            fg_color="#542b2b",
            hover_color="#542b2b",
            state="disabled",
        )
        self.abort_button.grid(row=0, column=2, sticky="e")
        self._add_tooltip(self.abort_button, "Abort flash")
        self.log_actions = ctk.CTkFrame(console_frame, fg_color="transparent")
        self.log_actions.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 6))
        self.log_actions.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.log_actions, text="Logs", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0,
            column=0,
            sticky="w",
        )
        flash_clear_button = ctk.CTkButton(
            self.log_actions,
            text="",
            image=self._icons["clear"],
            command=self.clear_log,
            width=30,
            height=30,
            corner_radius=6,
        )
        flash_clear_button.grid(row=0, column=1, padx=4)
        self._add_tooltip(flash_clear_button, "Clear logs")
        flash_save_button = ctk.CTkButton(
            self.log_actions,
            text="",
            image=self._icons["save"],
            command=self.save_log,
            width=30,
            height=30,
            corner_radius=6,
        )
        flash_save_button.grid(row=0, column=2)
        self._add_tooltip(flash_save_button, "Download logs")
        self.console = ctk.CTkTextbox(console_frame, font=("Consolas", 12), wrap="word")
        self.console.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.console.configure(state="disabled")
        self.console.grid_remove()
        self.log_actions.grid_remove()
        self._build_monitor_view()
        self.show_monitor()

    def _build_monitor_view(self) -> None:
        """Build the dedicated serial-monitor workspace below device discovery."""
        self.monitor_view = ctk.CTkFrame(self.view_area)  # pyright: ignore[reportAttributeAccessIssue]
        self.monitor_view.grid(row=0, column=0, sticky="nsew")
        self.monitor_view.grid_columnconfigure(0, weight=1)
        self.monitor_view.grid_rowconfigure(1, weight=1)

        controls = ctk.CTkFrame(self.monitor_view, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8))
        controls.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(controls, text="Monitor", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(controls, text="Buad Rate").grid(row=0, column=1, padx=(18, 4))
        ctk.CTkOptionMenu(controls, variable=self.monitor_baud_var, values=list(BAUD_RATES), width=110).grid(
            row=0, column=2, sticky="w"
        )
        ctk.CTkLabel(controls, textvariable=self.monitor_status_var).grid(row=0, column=3, padx=10, sticky="e")
        self.monitor_connect_button = ctk.CTkButton(  # pyright: ignore[reportAttributeAccessIssue]
            controls,
            text="Connect",
            command=self.toggle_monitor_connection,
            fg_color="#3a7ebf",
            hover_color="#325882",
        )
        self.monitor_connect_button.grid(row=0, column=4, padx=(0, 8))
        monitor_clear_button = ctk.CTkButton(
            controls,
            text="",
            image=self._icons["clear"],
            command=self.clear_monitor_log,
            width=30,
            height=30,
            corner_radius=6,
        )
        monitor_clear_button.grid(row=0, column=5, padx=4)
        self._add_tooltip(monitor_clear_button, "Clear logs")
        monitor_save_button = ctk.CTkButton(
            controls,
            text="",
            image=self._icons["save"],
            command=self.save_monitor_log,
            width=30,
            height=30,
            corner_radius=6,
        )
        monitor_save_button.grid(row=0, column=6)
        self._add_tooltip(monitor_save_button, "Download logs")

        self.monitor_console = ctk.CTkTextbox(  # pyright: ignore[reportAttributeAccessIssue]
            self.monitor_view,
            font=("Consolas", 12),
            wrap="word",
        )
        self.monitor_console.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 8))
        self.monitor_console.configure(state="disabled")
        command_frame = ctk.CTkFrame(self.monitor_view, fg_color="transparent")
        command_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        command_frame.grid_columnconfigure(0, weight=1)
        command_entry = ctk.CTkEntry(command_frame, textvariable=self.monitor_input_var, placeholder_text="Send exact serial text")
        command_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        command_entry.bind("<Return>", self.send_monitor_input)
        self.monitor_send_button = ctk.CTkButton(  # pyright: ignore[reportAttributeAccessIssue]
            command_frame,
            text="Send",
            command=self.send_monitor_input,
            width=90,
            state="disabled",
        )
        self.monitor_send_button.grid(row=0, column=1)

    def show_monitor(self) -> None:
        """Display the serial monitor while retaining the flash configuration."""
        self.flash_view.grid_remove()
        self.monitor_view.grid()
        self.monitor_nav.configure(fg_color=("#3a7ebf", "#1f6aa5"))
        self.flash_nav.configure(fg_color="transparent")
        self.geometry("1040x650")

    def show_flash(self) -> None:
        """Display the firmware flashing workspace while retaining monitor state."""
        self.monitor_view.grid_remove()
        self.flash_view.grid()
        self.flash_nav.configure(fg_color=("#3a7ebf", "#1f6aa5"))
        self.monitor_nav.configure(fg_color="transparent")
        self.geometry("1040x540")

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
        action_slot = ctk.CTkFrame(row, width=30, height=30, fg_color="transparent")
        action_slot.grid(row=0, column=4, padx=(4, 0))
        action_slot.grid_propagate(False)
        remove_button = ctk.CTkButton(
            action_slot,
            text="",
            image=self._icons["abort"],
            width=30,
            height=30,
            corner_radius=6,
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
        self._add_tooltip(remove_button, "Remove partition")
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

    def _selected_port(self) -> str:
        """Extract the COM ID from the currently selected discovery entry."""
        selected = self.port_var.get().split(" | ")
        return selected[1] if len(selected) == 3 else ""

    def toggle_monitor_connection(self) -> None:
        """Connect the monitor to the selected port or disconnect an active session."""
        if self._monitor_serial is not None:
            self.disconnect_monitor()
            return
        if self._active_process is not None:
            self._write_monitor_log("Wait for the flash operation to finish before connecting the monitor.\n")
            return
        port = self._selected_port()
        if not port:
            self._write_monitor_log("Select a serial device before connecting.\n")
            return
        try:
            connection = serial.Serial(port=port, baudrate=int(self.monitor_baud_var.get()), timeout=0.2)
        except (serial.SerialException, ValueError, OSError) as error:
            LOGGER.error("Could not connect serial monitor: %s", error)
            self._write_monitor_log(f"Could not connect to {port}: {error}\n")
            return
        self._monitor_serial = connection
        self._monitor_port = port
        self._monitor_stop.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_worker, daemon=True)
        self._monitor_thread.start()
        self.monitor_status_var.set(f"Connected to {port}")
        self.monitor_connect_button.configure(text="Disconnect", fg_color="#b53434", hover_color="#8e2727")
        self.monitor_send_button.configure(state="normal")
        self._write_monitor_log(f"Connected to {port} at {self.monitor_baud_var.get()} baud.\n")

    def _monitor_worker(self) -> None:
        """Read serial data in the background and pass decoded output to Tk."""
        while not self._monitor_stop.is_set():
            connection = self._monitor_serial
            if connection is None:
                break
            try:
                data = connection.read(connection.in_waiting or 1)
            except (serial.SerialException, OSError) as error:
                self._event_queue.put(("monitor-error", str(error)))
                break
            if data:
                self._event_queue.put(("monitor", data.decode("utf-8", errors="replace")))

    def disconnect_monitor(self) -> None:
        """Stop receiving and close the active serial monitor connection."""
        self._monitor_stop.set()
        connection = self._monitor_serial
        self._monitor_serial = None
        self._monitor_port = None
        if connection is not None:
            try:
                connection.close()
            except serial.SerialException as error:
                LOGGER.warning("Could not close serial monitor: %s", error)
        self.monitor_status_var.set("Disconnected")
        self.monitor_connect_button.configure(text="Connect", fg_color="#3a7ebf", hover_color="#325882")
        self.monitor_send_button.configure(state="disabled")
        self._write_monitor_log("Disconnected.\n")

    def send_monitor_input(self, _event: object | None = None) -> str | None:
        """Send monitor input exactly as written without appending line endings."""
        connection = self._monitor_serial
        message = self.monitor_input_var.get()
        if connection is None:
            self._write_monitor_log("Connect the monitor before sending data.\n")
            return "break" if _event is not None else None
        try:
            connection.write(message.encode("utf-8"))
        except (serial.SerialException, OSError) as error:
            LOGGER.error("Could not send monitor data: %s", error)
            self._write_monitor_log(f"Send failed: {error}\n")
            self.disconnect_monitor()
        else:
            self.monitor_input_var.set("")
        return "break" if _event is not None else None

    def clear_monitor_log(self) -> None:
        """Clear all retained serial-monitor output."""
        self.monitor_console.configure(state="normal")
        self.monitor_console.delete("1.0", "end")
        self.monitor_console.configure(state="disabled")

    def save_monitor_log(self) -> None:
        """Save retained serial-monitor output to a user-selected text file."""
        destination = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not destination:
            return
        try:
            Path(destination).write_text(self.monitor_console.get("1.0", "end-1c"), encoding="utf-8")
        except OSError as error:
            LOGGER.error("Could not save monitor log: %s", error)
            self._write_monitor_log(f"Could not save log: {error}\n")
            return
        self._write_monitor_log(f"Log saved: {destination}\n")

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
                    esptool_worker_command(["--port", port.device, "read-mac"]),
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
        port = self._selected_port()
        if not port:
            self._write_console("Select a serial device before flashing.\n")
            return
        if self._monitor_serial is not None:
            if self._monitor_port == port:
                self._show_monitor_warning()
            else:
                self._write_console("Disconnect the active serial monitor before flashing another device.\n")
            return
        arguments = ["--chip", "auto", "--port", port, "--baud", self.baud_var.get(), "write-flash"]
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
        self.abort_button.configure(state="normal", fg_color="#b53434", hover_color="#8e2727")
        self._write_console(f"$ {' '.join(esptool_worker_command(arguments))}\n")
        threading.Thread(target=self._flash_worker, args=(arguments,), daemon=True).start()

    def _show_monitor_warning(self) -> None:
        """Ask whether to disconnect the selected monitored device before flashing."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Monitor Connected")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(
            dialog,
            text="The selected device is connected to Monitor.\nDisconnect it before starting the flash operation?",
            justify="center",
        ).pack(padx=28, pady=(24, 18))
        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.pack(padx=20, pady=(0, 20))
        ctk.CTkButton(
            actions,
            text="Disconnect and Proceed",
            command=lambda: self._disconnect_and_flash(dialog),
        ).pack(side="left", padx=4)
        ctk.CTkButton(actions, text="Cancel", command=dialog.destroy, fg_color="transparent", border_width=1).pack(
            side="left", padx=4
        )

    def _disconnect_and_flash(self, dialog: ctk.CTkToplevel) -> None:
        """Close the warning, disconnect Monitor, and resume the flash request."""
        dialog.destroy()
        self.disconnect_monitor()
        self.flash_program()

    def _flash_worker(self, arguments: list[str]) -> None:
        """Run esptool, forwarding its combined output to the UI queue."""
        try:
            with self._process_lock:
                self._active_process = subprocess.Popen(
                    esptool_worker_command(arguments),
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
            self._set_abort_disabled()
            return
        process.terminate()
        self.status_var.set("Aborting...")
        self._set_abort_disabled()
        self._write_console("Abort requested.\n")

    def _set_abort_disabled(self) -> None:
        """Dim and disable Abort whenever no flash process can be terminated."""
        self.abort_button.configure(state="disabled", fg_color="#542b2b", hover_color="#542b2b")

    def toggle_log(self) -> None:
        """Toggle the retained log panel and update its directional control."""
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.grid_rowconfigure(2, weight=1)
            self.geometry("1040x720")
            self.log_actions.grid()
            self.console.grid()
            self.log_toggle.configure(image=self._icons["minimize"])
            self.log_tooltip.text = "Minimize logs"
        else:
            self.grid_rowconfigure(2, weight=0)
            self.geometry("1040x540")
            self.log_actions.grid_remove()
            self.console.grid_remove()
            self.log_toggle.configure(image=self._icons["expand"])
            self.log_tooltip.text = "Maximize logs"

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
            elif event == "monitor":
                self._write_monitor_log(value)
            elif event == "monitor-error":
                self._write_monitor_log(f"Monitor connection lost: {value}\n")
                self.disconnect_monitor()
            elif event == "devices":
                devices = [device.split("\t") for device in value.splitlines()]
                self._display_devices(devices)
                self.status_var.set(f"Found {len(devices)} serial device(s)")
                self._write_console(f"Scan complete: {len(devices)} serial device(s) found.\n")
            elif event == "complete":
                self.status_var.set("Ready" if value == "0" else f"Flash ended ({value})")
                self._set_abort_disabled()
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

    def _write_monitor_log(self, message: str) -> None:
        """Append text to the read-only serial monitor and reveal its latest output."""
        self.monitor_console.configure(state="normal")
        self.monitor_console.insert("end", message)
        self.monitor_console.see("end")
        self.monitor_console.configure(state="disabled")

    def close_application(self) -> None:
        """Close active device resources before destroying the main window."""
        if self._monitor_serial is not None:
            self.disconnect_monitor()
        with self._process_lock:
            process = self._active_process
        if process is not None and process.poll() is None:
            process.terminate()
        self.destroy()


def main() -> None:
    """Configure logging and run the Espress View application."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not acquire_single_instance():
        LOGGER.warning("Espress View is already running")
        return
    application = EspressView()
    try:
        application.mainloop()
    except KeyboardInterrupt:
        LOGGER.warning("Application interrupted from the terminal")
        application.close_application()
    finally:
        release_single_instance()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--esptool-worker":
        raise SystemExit(run_esptool_worker(sys.argv[2:]))
    main()