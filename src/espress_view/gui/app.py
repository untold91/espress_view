#!/usr/bin/env python3
"""CustomTkinter frontend for device discovery, monitoring, and flashing."""

import logging
import queue
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import Event, TclError, filedialog

import customtkinter as ctk
import serial
from PIL import Image, ImageTk

from espress_view.config import BAUD_RATES, MAX_PARTITIONS
from espress_view.core import serial_monitor
from espress_view.core.device_discovery import discover_devices
from espress_view.flasher.arguments import build_flash_arguments
from espress_view.flasher.runner import FlashRunner, esptool_worker_command
from espress_view.utils.paths import resource_path
from espress_view.utils.settings import AppSettings
from espress_view.gui.design import (
    FONT_FAMILY,
    MONOSPACE_FAMILY,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
    SPACE_XS,
    color,
)
from espress_view.gui.icons import ICON_NAMES, load_icon
from espress_view.gui.widgets import ChevronOptionMenu

LOGGER = logging.getLogger(__name__)
MAX_CONSOLE_LINES = 5000
MAX_CONSOLE_CHARS = 1_000_000
EVENT_BATCH_SIZE = 500


@dataclass
class Partition:
    """Store the widgets and values for one firmware partition."""

    row: ctk.CTkFrame
    index_label: ctk.CTkLabel
    file_path: ctk.StringVar
    address: ctk.StringVar
    file_entry: ctk.CTkEntry
    address_entry: ctk.CTkEntry
    browse_button: ctk.CTkButton
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
        self.widget.bind("<FocusIn>", self.schedule_show, add="+")
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
        self._settings = AppSettings()
        initial_view = self._settings.last_view
        ctk.set_appearance_mode(self._settings.theme.title())
        super().__init__()
        self.title("Espress View")
        self.configure(fg_color=color("window"))
        self.minsize(900, 600)
        self._restore_window_size()
        self._application_icon = ImageTk.PhotoImage(Image.open(resource_path("icons", "exe-file.ico")))
        self.iconphoto(True, self._application_icon)
        self._flash_runner = FlashRunner()
        self._flash_thread: threading.Thread | None = None
        self._flash_busy = False
        self._flash_abort_requested = threading.Event()
        self._scan_active = False
        self._closing = False
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
        flash_baud = self._settings.flash_baud
        monitor_baud = self._settings.monitor_baud
        self.baud_var = ctk.StringVar(value=flash_baud if flash_baud in BAUD_RATES else "2000000")
        self.monitor_baud_var = ctk.StringVar(value=monitor_baud if monitor_baud in BAUD_RATES else "115200")
        self.monitor_input_var = ctk.StringVar()
        self.monitor_status_var = ctk.StringVar(value="Disconnected")
        self.status_var = ctk.StringVar(value="Ready")
        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_text_var = ctk.StringVar(value="Waiting for progress")
        self.device_status_var = ctk.StringVar(value="Scanning for ESP devices…")
        self.log_visible = False
        self._event_after_id: str | None = None
        self._icons = self._load_icons()
        self._action_icons = self._load_action_icons()
        self._status_icons = self._load_status_icons()
        self._build_interface()
        self._set_flash_status("Ready")
        self.protocol("WM_DELETE_WINDOW", self.close_application)
        self._drain_events()
        self.after(200, self.scan_devices)
        if self._settings.show_flash_logs:
            self.toggle_log()
        if initial_view == "flash":
            self.show_flash()

    def _restore_window_size(self) -> None:
        """Restore only a plausible saved size that fits the current display."""
        try:
            width, height = self._settings.window_size
        except (TypeError, ValueError):
            LOGGER.warning("Ignoring invalid saved window size")
            width, height = 1040, 650
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        if width < 900 or height < 600 or width > screen_width or height > screen_height:
            width, height = min(1040, screen_width), min(650, screen_height)
        self.geometry(f"{width}x{height}")

    @staticmethod
    def _add_tooltip(widget: ctk.CTkBaseClass, text: str) -> None:
        """Attach a concise hover tooltip to an icon-only control."""
        Tooltip(widget, text)

    @staticmethod
    def _add_focus_indicator(widget: ctk.CTkBaseClass) -> None:
        """Show an accent outline while a keyboard-operable control has focus."""
        base_width = widget.cget("border_width")
        base_color = widget.cget("border_color")
        widget.bind(
            "<FocusIn>",
            lambda _event: widget.configure(border_width=2, border_color=color("accent")),
            add="+",
        )
        widget.bind(
            "<FocusOut>",
            lambda _event: widget.configure(border_width=base_width, border_color=base_color),
            add="+",
        )

    @staticmethod
    def _add_focus_fill_indicator(widget: ctk.CTkBaseClass) -> None:
        """Highlight focus for CustomTkinter controls without configurable borders."""
        base_color = widget.cget("fg_color")
        widget.bind(
            "<FocusIn>",
            lambda _event: widget.configure(fg_color=color("accent_subtle")),
            add="+",
        )
        widget.bind(
            "<FocusOut>",
            lambda _event: widget.configure(fg_color=base_color),
            add="+",
        )

    def _load_icons(self) -> dict[str, ctk.CTkImage]:
        """Load bundled Lucide icons with theme-aware foreground colours."""
        light_color = color("text_secondary")[0]
        dark_color = color("text_secondary")[1]
        return {
            name: ctk.CTkImage(
                light_image=load_icon(name, light_color, (96, 96)),
                dark_image=load_icon(name, dark_color, (96, 96)),
                size=(18, 18),
            )
            for name in ICON_NAMES
        }

    def _load_status_icons(self) -> dict[str, ctk.CTkImage]:
        """Create status icons using the semantic status colours in each theme."""
        variants = {
            "Ready": ("plug", "text_muted"),
            "Starting": ("plug", "accent"),
            "Flashing": ("zap", "accent"),
            "Flashed": ("circle-check", "success"),
            "Aborted": ("circle-x", "warning"),
            "Failed": ("circle-alert", "error"),
            "Aborting": ("circle-alert", "warning"),
        }
        return {
            status: ctk.CTkImage(
                light_image=load_icon(icon, color(token)[0], (72, 72)),
                dark_image=load_icon(icon, color(token)[1], (72, 72)),
                size=(16, 16),
            )
            for status, (icon, token) in variants.items()
        }

    def _load_action_icons(self) -> dict[str, ctk.CTkImage]:
        """Tint primary-action icons for the foreground on their themed buttons."""
        return {
            name: ctk.CTkImage(
                light_image=load_icon(name, color("accent_text")[0], (96, 96)),
                dark_image=load_icon(name, color("accent_text")[1], (96, 96)),
                size=(18, 18),
            )
            for name in ("plug", "unplug")
        }
    def _build_interface(self) -> None:
        """Build the shared application shell and both workspaces."""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        navigation = ctk.CTkFrame(
            self,
            width=176,
            fg_color=color("sidebar"),
            corner_radius=12,
            border_width=1,
            border_color=color("border"),
        )
        navigation.grid(row=0, column=0, sticky="ns", padx=(SPACE_LG, SPACE_SM), pady=SPACE_LG)
        navigation.grid_propagate(False)
        brand = ctk.CTkFrame(navigation, fg_color="transparent")
        brand.pack(fill="x", padx=SPACE_LG, pady=(SPACE_XL, SPACE_XL + SPACE_SM))
        ctk.CTkLabel(
            brand,
            text="Espress View",
            font=ctk.CTkFont(family=FONT_FAMILY, size=19, weight="bold"),
            text_color=color("text"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand,
            text="ESP device toolkit",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=color("text_muted"),
        ).pack(anchor="w", pady=(3, 0))
        ctk.CTkLabel(
            navigation,
            text="WORKSPACES",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=color("text_muted"),
        ).pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_SM))
        navigation_actions = ctk.CTkFrame(navigation, fg_color="transparent")
        navigation_actions.pack(fill="x", padx=SPACE_SM)
        self.monitor_nav = ctk.CTkButton(
            navigation_actions,
            text="Monitor",
            image=self._icons["monitor"],
            compound="left",
            command=self.show_monitor,
            anchor="w",
            height=40,
            corner_radius=8,
            fg_color="transparent",
            hover_color=color("accent_subtle"),
            text_color=color("text_secondary"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
        )
        self.monitor_nav.pack(fill="x", pady=3)
        self._add_focus_indicator(self.monitor_nav)
        self.flash_nav = ctk.CTkButton(
            navigation_actions,
            text="Flash",
            image=self._icons["zap"],
            compound="left",
            command=self.show_flash,
            anchor="w",
            height=40,
            corner_radius=8,
            fg_color="transparent",
            hover_color=color("accent_subtle"),
            text_color=color("text_secondary"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
        )
        self.flash_nav.pack(fill="x", pady=3)
        self._add_focus_indicator(self.flash_nav)
        sidebar_footer = ctk.CTkFrame(navigation, fg_color="transparent")
        sidebar_footer.pack(side="bottom", fill="x", padx=SPACE_MD, pady=SPACE_MD)
        ctk.CTkLabel(
            sidebar_footer,
            text="APPEARANCE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=color("text_muted"),
        ).pack(anchor="w", padx=2, pady=(0, 6))
        self.theme_var = ctk.StringVar(value=self._settings.theme)
        self.theme_selector = ctk.CTkFrame(
            sidebar_footer,
            fg_color=color("surface"),
            corner_radius=8,
            border_width=1,
            border_color=color("border"),
        )
        self.theme_selector.pack(fill="x")
        self.theme_buttons: dict[str, ctk.CTkButton] = {}
        for column, (mode, icon_name) in enumerate(
            (("light", "sun"), ("system", "monitor"), ("dark", "moon"))
        ):
            self.theme_selector.grid_columnconfigure(column, weight=1, uniform="appearance")
            button = ctk.CTkButton(
                self.theme_selector,
                text="",
                image=self._icons[icon_name],
                command=lambda selected=mode: self._change_theme(selected),
                width=44,
                height=38,
                corner_radius=6,
                fg_color="transparent",
                hover_color=color("accent_subtle"),
                text_color=color("text_secondary"),
            )
            button.appearance_accessible_name = f"{mode.title()} appearance"
            button.grid(row=0, column=column, sticky="ew", padx=2, pady=2)
            self.theme_buttons[mode] = button
            self._add_tooltip(button, f"{mode.title()} appearance")
            self._add_focus_indicator(button)
        self._sync_appearance_selector()

        main_area = ctk.CTkFrame(self, fg_color="transparent")
        main_area.grid(row=0, column=1, sticky="nsew", padx=(0, SPACE_LG), pady=SPACE_LG)
        main_area.grid_columnconfigure(0, weight=1)
        main_area.grid_rowconfigure(1, weight=1)

        device_frame = ctk.CTkFrame(
            main_area,
            fg_color=color("surface"),
            corner_radius=10,
            border_width=1,
            border_color=color("border"),
        )
        device_frame.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))
        device_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            device_frame,
            text="TARGET DEVICE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=color("text_muted"),
        ).grid(row=0, column=0, sticky="w", padx=(14, 10), pady=(10, 2))
        self.device_status_label = ctk.CTkLabel(
            device_frame,
            textvariable=self.device_status_var,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=color("text_muted"),
        )
        self.device_status_label.grid(row=0, column=1, sticky="e", padx=14, pady=(10, 2))
        self.port_menu = ChevronOptionMenu(
            device_frame,
            variable=self.port_var,
            values=["No device selected"],
            height=36,
            fg_color=color("surface_alt"),
            button_color=color("surface_alt"),
            button_hover_color=color("accent_subtle"),
            text_color=color("text"),
            dropdown_fg_color=color("surface"),
            dropdown_text_color=color("text"),
            dropdown_hover_color=color("accent_subtle"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
        )
        self.port_menu.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(14, 8), pady=(2, 10))
        self._add_focus_fill_indicator(self.port_menu)
        self.scan_button = ctk.CTkButton(
            device_frame,
            text="Rescan",
            image=self._icons["refresh-cw"],
            command=self.scan_devices,
            width=96,
            height=36,
            corner_radius=8,
            fg_color=color("surface_alt"),
            hover_color=color("accent_subtle"),
            text_color=color("text"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
        )
        self.scan_button.grid(row=1, column=2, padx=(0, 14), pady=(2, 10))
        self._add_focus_indicator(self.scan_button)

        self.view_area = ctk.CTkFrame(main_area, fg_color="transparent")
        self.view_area.grid(row=1, column=0, sticky="nsew")
        self.view_area.grid_columnconfigure(0, weight=1)
        self.view_area.grid_rowconfigure(0, weight=1)
        self._build_flash_view()
        self._build_monitor_view()
        self.show_monitor()

    def _build_flash_view(self) -> None:
        """Build firmware configuration, progress, and the collapsible console."""
        self.flash_view = ctk.CTkFrame(self.view_area, fg_color="transparent")
        self.flash_view.grid(row=0, column=0, sticky="nsew")
        self.flash_view.grid_columnconfigure(0, weight=1)
        self.flash_view.grid_rowconfigure(1, weight=1)

        page_header = ctk.CTkFrame(self.flash_view, fg_color="transparent")
        page_header.grid(row=0, column=0, sticky="ew", pady=(SPACE_XS, SPACE_MD))
        page_header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            page_header,
            text="Flash firmware",
            font=ctk.CTkFont(family=FONT_FAMILY, size=24, weight="bold"),
            text_color=color("text"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            page_header,
            text="Configure firmware images and program the selected device.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=color("text_secondary"),
            anchor="e",
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

        workspace = ctk.CTkFrame(
            self.flash_view,
            fg_color=color("surface"),
            corner_radius=10,
            border_width=1,
            border_color=color("border"),
        )
        self.flash_workspace = workspace
        workspace.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        workspace.grid_columnconfigure(0, weight=1)
        workspace.grid_rowconfigure(1, weight=1)
        workspace_header = ctk.CTkFrame(workspace, fg_color="transparent")
        workspace_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 2))
        workspace_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            workspace_header,
            text="Firmware configuration",
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            text_color=color("text"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            workspace_header,
            text=f"Up to {MAX_PARTITIONS} images",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=color("text_muted"),
        ).grid(row=0, column=1, sticky="e")
        self.add_partition_button = ctk.CTkButton(
            workspace_header,
            text="Add partition",
            command=self.add_partition,
            width=126,
            height=30,
            corner_radius=7,
            fg_color="transparent",
            hover_color=color("accent_subtle"),
            border_width=1,
            border_color=color("border"),
            text_color=color("text_secondary"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
        )
        self.add_partition_button.grid(row=0, column=2, padx=(12, 0))
        self._add_focus_indicator(self.add_partition_button)
        self.partitions_frame = ctk.CTkScrollableFrame(
            workspace,
            height=128,
            fg_color="transparent",
            scrollbar_button_color=color("border"),
            scrollbar_button_hover_color=color("text_muted"),
        )
        self.partitions_frame.grid(row=1, column=0, sticky="nsew", padx=(10, 6), pady=(0, 4))
        for column, width in ((0, 34), (2, 84), (3, 118), (4, 34)):
            self.partitions_frame.grid_columnconfigure(column, minsize=width)
        self.partitions_frame.grid_columnconfigure(1, weight=1)
        self.add_partition()

        flash_controls = ctk.CTkFrame(
            self.flash_view,
            fg_color=color("surface"),
            corner_radius=10,
            border_width=1,
            border_color=color("border"),
        )
        flash_controls.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        flash_controls.grid_columnconfigure(3, weight=1)
        self.flash_baud_label = ctk.CTkLabel(
            flash_controls,
            text="Flash baud",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=color("text_secondary"),
        )
        self.flash_baud_label.grid(row=0, column=0, padx=(12, 6), pady=8)
        self.baud_menu = ChevronOptionMenu(
            flash_controls,
            variable=self.baud_var,
            values=list(BAUD_RATES),
            width=122,
            height=34,
            fg_color=color("surface_alt"),
            button_color=color("surface_alt"),
            button_hover_color=color("accent_subtle"),
            text_color=color("text"),
            dropdown_fg_color=color("surface"),
            dropdown_text_color=color("text"),
            dropdown_hover_color=color("accent_subtle"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            command=self._save_flash_baud,
        )
        self.baud_menu.grid(row=0, column=1, padx=(0, 8), pady=8)
        self.status_label = ctk.CTkLabel(
            flash_controls,
            textvariable=self.status_var,
            compound="left",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=color("text_muted"),
        )
        self.status_label.grid(row=0, column=2, padx=(2, 10), sticky="w")
        self.flash_button = ctk.CTkButton(
            flash_controls,
            text="Flash Program",
            image=self._icons["zap"],
            compound="left",
            command=self.flash_program,
            width=150,
            height=34,
            corner_radius=8,
            fg_color=color("accent"),
            hover_color=color("accent_hover"),
            text_color=color("accent_text"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
        )
        self.flash_button.grid(row=0, column=4, padx=(8, 12), pady=8)
        self._add_focus_indicator(self.flash_button)
        self._add_focus_fill_indicator(self.baud_menu)

        self.flash_progress_area = ctk.CTkFrame(flash_controls, fg_color="transparent")
        self.flash_progress_area.grid(row=1, column=0, columnspan=5, sticky="ew", padx=12, pady=(0, 10))
        self.flash_progress_area.grid_columnconfigure(0, weight=1)
        self.progress = ctk.CTkProgressBar(
            self.flash_progress_area,
            variable=self.progress_var,
            height=10,
            progress_color=color("accent"),
            fg_color=color("disabled"),
        )
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.progress_text_label = ctk.CTkLabel(
            self.flash_progress_area,
            textvariable=self.progress_text_var,
            width=100,
            anchor="e",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=color("text_muted"),
        )
        self.progress_text_label.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.abort_button = ctk.CTkButton(
            self.flash_progress_area,
            text="Abort",
            image=self._icons["circle-x"],
            compound="left",
            command=self.abort_flash,
            width=86,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            hover_color=color("accent_subtle"),
            text_color=color("error"),
            state="disabled",
        )
        self.abort_button.grid(row=0, column=2, padx=(0, 2))
        self._add_focus_indicator(self.abort_button)
        self.flash_progress_area.grid_remove()

        self.console_frame = ctk.CTkFrame(
            self.flash_view,
            fg_color=color("surface"),
            corner_radius=10,
            border_width=1,
            border_color=color("border"),
        )
        self.console_frame.grid(row=3, column=0, sticky="nsew")
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(1, weight=1)
        console_header = ctk.CTkFrame(self.console_frame, fg_color="transparent")
        console_header.grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        console_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            console_header,
            text="Flash output",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=color("text"),
        ).grid(row=0, column=0, sticky="w", padx=4)
        clear_button = ctk.CTkButton(
            console_header,
            text="Clear",
            image=self._icons["trash-2"],
            compound="left",
            command=self.clear_log,
            width=74,
            height=30,
            corner_radius=7,
            fg_color="transparent",
            hover_color=color("accent_subtle"),
            text_color=color("text_secondary"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        )
        clear_button.grid(row=0, column=1, padx=2)
        self._add_focus_indicator(clear_button)
        export_button = ctk.CTkButton(
            console_header,
            text="Export",
            image=self._icons["save"],
            compound="left",
            command=self.save_log,
            width=78,
            height=30,
            corner_radius=7,
            fg_color="transparent",
            hover_color=color("accent_subtle"),
            text_color=color("text_secondary"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        )
        export_button.grid(row=0, column=2, padx=2)
        self._add_focus_indicator(export_button)
        self.log_toggle = ctk.CTkButton(
            console_header,
            text="",
            image=self._icons["chevron-up"],
            command=self.toggle_log,
            width=30,
            height=30,
            corner_radius=7,
            fg_color="transparent",
            hover_color=color("accent_subtle"),
        )
        self.log_toggle.grid(row=0, column=3, padx=(2, 0))
        self._add_focus_indicator(self.log_toggle)
        self.log_tooltip = Tooltip(self.log_toggle, "Show flash output")
        self.console = ctk.CTkTextbox(
            self.console_frame,
            height=80,
            font=(MONOSPACE_FAMILY, 12),
            wrap="word",
            fg_color=color("terminal"),
            text_color=color("terminal_text"),
            border_width=1,
            border_color=color("border"),
            corner_radius=8,
        )
        self.console.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.console.configure(state="disabled")
        self.console.grid_remove()

    def _build_monitor_view(self) -> None:
        """Build the live serial terminal and exact-text command input."""
        self.monitor_view = ctk.CTkFrame(self.view_area, fg_color="transparent")
        self.monitor_view.grid(row=0, column=0, sticky="nsew")
        self.monitor_view.grid_columnconfigure(0, weight=1)
        self.monitor_view.grid_rowconfigure(2, weight=1)

        page_header = ctk.CTkFrame(self.monitor_view, fg_color="transparent")
        page_header.grid(row=0, column=0, sticky="ew", pady=(SPACE_XS, SPACE_MD))
        page_header.grid_columnconfigure(1, weight=1)
        self.monitor_heading = ctk.CTkLabel(
            page_header,
            text="Serial Monitor",
            font=ctk.CTkFont(family=FONT_FAMILY, size=24, weight="bold"),
            text_color=color("text"),
        )
        self.monitor_heading.grid(row=0, column=0, sticky="w")
        self.monitor_description = ctk.CTkLabel(
            page_header,
            text="Inspect live output and send exact UTF-8 text to the connected device.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=color("text_secondary"),
            anchor="e",
        )
        self.monitor_description.grid(row=0, column=1, sticky="e", padx=(12, 0))
        page_header.bind("<Configure>", self._layout_monitor_heading, add="+")

        controls = ctk.CTkFrame(
            self.monitor_view,
            fg_color=color("surface"),
            corner_radius=10,
            border_width=1,
            border_color=color("border"),
        )
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        controls.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(
            controls,
            text="Baud rate",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=color("text_secondary"),
        ).grid(row=0, column=0, padx=(12, 6), pady=10)
        self.monitor_baud_menu = ChevronOptionMenu(
            controls,
            variable=self.monitor_baud_var,
            values=list(BAUD_RATES),
            width=116,
            height=34,
            fg_color=color("surface_alt"),
            button_color=color("surface_alt"),
            button_hover_color=color("accent_subtle"),
            text_color=color("text"),
            dropdown_fg_color=color("surface"),
            dropdown_text_color=color("text"),
            dropdown_hover_color=color("accent_subtle"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            command=self._save_monitor_baud,
        )
        self.monitor_baud_menu.grid(row=0, column=1, padx=(0, 10), pady=8)
        self._add_focus_fill_indicator(self.monitor_baud_menu)
        self.monitor_status_label = ctk.CTkLabel(
            controls,
            textvariable=self.monitor_status_var,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=color("text_muted"),
        )
        self.monitor_status_label.grid(row=0, column=2, padx=(6, 8), sticky="e")
        self.monitor_connect_button = ctk.CTkButton(
            controls,
            text="Connect",
            image=self._action_icons["plug"],
            compound="left",
            command=self.toggle_monitor_connection,
            width=104,
            height=34,
            corner_radius=8,
            fg_color=color("accent"),
            hover_color=color("accent_hover"),
            text_color=color("accent_text"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
        )
        self.monitor_connect_button.grid(row=0, column=4, padx=4, pady=8)
        self._add_focus_indicator(self.monitor_connect_button)
        monitor_clear_button = ctk.CTkButton(
            controls,
            text="Clear",
            image=self._icons["trash-2"],
            compound="left",
            command=self.clear_monitor_log,
            width=76,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=color("accent_subtle"),
            text_color=color("text_secondary"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        )
        monitor_clear_button.grid(row=0, column=5, padx=2, pady=8)
        self._add_focus_indicator(monitor_clear_button)
        monitor_save_button = ctk.CTkButton(
            controls,
            text="Export",
            image=self._icons["save"],
            compound="left",
            command=self.save_monitor_log,
            width=80,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=color("accent_subtle"),
            text_color=color("text_secondary"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        )
        monitor_save_button.grid(row=0, column=6, padx=(2, 10), pady=8)
        self._add_focus_indicator(monitor_save_button)

        terminal = ctk.CTkFrame(
            self.monitor_view,
            fg_color=color("surface"),
            corner_radius=10,
            border_width=1,
            border_color=color("border"),
        )
        terminal.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        terminal.grid_columnconfigure(0, weight=1)
        terminal.grid_rowconfigure(0, weight=1)
        self.monitor_console = ctk.CTkTextbox(
            terminal,
            font=(MONOSPACE_FAMILY, 12),
            wrap="word",
            fg_color=color("terminal"),
            text_color=color("terminal_text"),
            border_width=1,
            border_color=color("border"),
            corner_radius=8,
        )
        self.monitor_console.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.monitor_console.configure(state="disabled")
        command_frame = ctk.CTkFrame(
            self.monitor_view,
            fg_color=color("surface"),
            corner_radius=10,
            border_width=1,
            border_color=color("border"),
        )
        command_frame.grid(row=3, column=0, sticky="ew")
        command_frame.grid_columnconfigure(0, weight=1)
        self.command_entry = ctk.CTkEntry(
            command_frame,
            textvariable=self.monitor_input_var,
            placeholder_text="Type a command (sent exactly as entered; no newline added)",
            height=36,
            state="disabled",
            fg_color=color("input"),
            border_color=color("border"),
            text_color=color("text"),
            placeholder_text_color=color("text_muted"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
        )
        self.command_entry.grid(row=0, column=0, sticky="ew", padx=(10, 8), pady=10)
        self._add_focus_indicator(self.command_entry)
        self.command_entry.bind("<Return>", self.send_monitor_input)
        self.monitor_send_button = ctk.CTkButton(
            command_frame,
            text="Send",
            command=self.send_monitor_input,
            width=86,
            height=36,
            corner_radius=8,
            fg_color=color("accent"),
            hover_color=color("accent_hover"),
            text_color=color("accent_text"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            state="disabled",
        )
        self.monitor_send_button.grid(row=0, column=1, padx=(0, 10), pady=10)
        self._add_focus_indicator(self.monitor_send_button)

    def show_monitor(self) -> None:
        """Display Monitor without changing the user's window geometry."""
        self.flash_view.grid_remove()
        self.monitor_view.grid()
        self.monitor_nav.configure(fg_color=color("accent_subtle"), text_color=color("accent"))
        self.flash_nav.configure(fg_color="transparent", text_color=color("text_secondary"))
        if hasattr(self, "_settings"):
            self._settings.last_view = "monitor"

    def show_flash(self) -> None:
        """Display Flash without changing the user's window geometry."""
        self.monitor_view.grid_remove()
        self.flash_view.grid()
        self.flash_nav.configure(fg_color=color("accent_subtle"), text_color=color("accent"))
        self.monitor_nav.configure(fg_color="transparent", text_color=color("text_secondary"))
        if hasattr(self, "_settings"):
            self._settings.last_view = "flash"

    def _change_theme(self, selected: str) -> None:
        """Apply and persist a Light, System, or Dark appearance preference."""
        mode = selected.lower().strip()
        if mode not in {"dark", "light", "system"}:
            raise ValueError(f"Unsupported appearance mode: {selected}")
        ctk.set_appearance_mode(mode.title())
        self.theme_var.set(mode)
        self._settings.theme = mode
        self._sync_appearance_selector()

    def _sync_appearance_selector(self) -> None:
        """Keep exactly one appearance segment selected."""
        selected = self.theme_var.get()
        for mode, button in self.theme_buttons.items():
            active = mode == selected
            button.configure(
                fg_color=color("accent_subtle") if active else "transparent",
                text_color=color("accent") if active else color("text_secondary"),
            )

    def _layout_monitor_heading(self, event: Event) -> None:
        """Wrap the description only when the heading row cannot fit on one line."""
        available_width = event.width - self.monitor_heading.winfo_reqwidth() - 24
        self.monitor_description.configure(wraplength=max(160, min(520, available_width)))

    def _set_flash_status(self, status: str) -> None:
        """Update the visible flash lifecycle state and its semantic icon."""
        if status not in self._status_icons:
            raise ValueError(f"Unsupported flash status: {status}")
        status_colors = {
            "Ready": "text_muted",
            "Starting": "accent",
            "Flashing": "accent",
            "Flashed": "success",
            "Aborted": "warning",
            "Failed": "error",
            "Aborting": "warning",
        }
        self.status_var.set(status)
        self.status_label.configure(
            image=self._status_icons[status],
            text_color=color(status_colors[status]),
        )

    def _save_monitor_baud(self, selected: str) -> None:
        """Persist the Monitor's independently selected baud rate."""
        self._settings.monitor_baud = selected

    def _save_flash_baud(self, selected: str) -> None:
        """Persist the firmware flashing baud rate."""
        self._settings.flash_baud = selected

    def add_partition(self) -> None:
        """Append a partition configuration row up to the supported maximum."""
        if len(self._partitions) >= MAX_PARTITIONS:
            self._write_console(f"A maximum of {MAX_PARTITIONS} partitions is supported.\n")
            return
        row = ctk.CTkFrame(self.partitions_frame, fg_color=color("surface_alt"), corner_radius=8)
        row.grid(row=len(self._partitions), column=0, columnspan=5, sticky="ew", pady=3, padx=(3, 7))
        row.grid_columnconfigure(1, weight=1)
        file_path = ctk.StringVar()
        address = ctk.StringVar(value="0x0000")
        index_label = ctk.CTkLabel(
            row,
            text=f"{len(self._partitions) + 1:02}",
            width=24,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=color("text_muted"),
        )
        index_label.grid(row=0, column=0, padx=(4, 2), pady=4)
        file_entry = ctk.CTkEntry(
            row,
            textvariable=file_path,
            placeholder_text="Firmware binary (.bin)",
            height=32,
            fg_color=color("input"),
            border_color=color("border"),
            text_color=color("text"),
            placeholder_text_color=color("text_muted"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        )
        file_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        browse_button = ctk.CTkButton(
            row,
            text="Browse",
            image=self._icons["folder-open"],
            compound="left",
            width=78,
            height=32,
            corner_radius=7,
            fg_color="transparent",
            hover_color=color("accent_subtle"),
            text_color=color("text_secondary"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        )
        browse_button.grid(row=0, column=2, padx=2, pady=4)
        self._add_focus_indicator(browse_button)
        address_entry = ctk.CTkEntry(
            row,
            textvariable=address,
            width=110,
            height=32,
            placeholder_text="0x1000",
            fg_color=color("input"),
            border_color=color("border"),
            text_color=color("text"),
            placeholder_text_color=color("text_muted"),
            font=(MONOSPACE_FAMILY, 11),
        )
        address_entry.grid(row=0, column=3, padx=4, pady=4)
        remove_button = ctk.CTkButton(
            row,
            text="",
            image=self._icons["trash-2"],
            width=30,
            height=30,
            corner_radius=7,
            fg_color="transparent",
            hover_color=color("accent_subtle"),
            text_color=color("error"),
        )
        partition = Partition(
            row=row,
            index_label=index_label,
            file_path=file_path,
            address=address,
            file_entry=file_entry,
            address_entry=address_entry,
            browse_button=browse_button,
            action_slot=row,
            remove_button=remove_button,
        )
        browse_button.configure(command=lambda: self._choose_file(partition))
        remove_button.configure(command=lambda: self.remove_partition(partition))
        remove_button.grid(row=0, column=4, padx=(0, 4), pady=4)
        self._add_focus_indicator(remove_button)
        self._add_tooltip(remove_button, "Remove partition")
        self._partitions.append(partition)
        self._refresh_partition_controls()

    def remove_partition(self, partition: Partition) -> None:
        """Remove a non-baseline partition row and renumber the remaining rows."""
        if self._flash_busy or not self._partitions or partition is self._partitions[0]:
            return
        partition.row.destroy()
        self._partitions.remove(partition)
        for index, current in enumerate(self._partitions):
            current.row.grid_configure(row=index)
            current.index_label.configure(text=f"{index + 1:02}")
        self._refresh_partition_controls()

    def _refresh_partition_controls(self) -> None:
        """Show removal controls only on partitions after the permanent first row."""
        for index, partition in enumerate(self._partitions):
            if index == 0:
                partition.remove_button.grid_remove()
            else:
                partition.remove_button.grid()
            state = "disabled" if self._flash_busy else "normal"
            partition.file_entry.configure(state=state)
            partition.address_entry.configure(state=state)
            partition.browse_button.configure(state=state)
            if index:
                partition.remove_button.configure(state=state)
        self.add_partition_button.configure(state="disabled" if self._flash_busy else "normal")

    def _choose_file(self, partition: Partition) -> None:
        """Open a file chooser and store the selected binary path."""
        if self._flash_busy:
            return
        selected = filedialog.askopenfilename(filetypes=[("Firmware binaries", "*.bin"), ("All files", "*.*")])
        if selected:
            partition.file_path.set(selected)

    def _selected_port(self) -> str:
        """Extract the COM ID from the currently selected discovery entry."""
        selected = self.port_var.get().split(" | ", maxsplit=2)
        return selected[1] if len(selected) == 3 else ""

    def toggle_monitor_connection(self) -> None:
        """Connect the monitor to the selected port or disconnect an active session."""
        if self._monitor_serial is not None:
            self.disconnect_monitor()
            return
        if self._flash_busy or self._scan_active:
            self._write_monitor_log("Wait for the flash operation to finish before connecting the monitor.\n")
            return
        port = self._selected_port()
        if not port:
            self._write_monitor_log("Select a serial device before connecting.\n")
            return
        try:
            connection = serial_monitor.connect(port, int(self.monitor_baud_var.get()))
        except (serial.SerialException, ValueError, OSError) as error:
            LOGGER.error("Could not connect serial monitor: %s", error)
            self._write_monitor_log(f"Could not connect to {port}: {error}\n")
            self.monitor_status_var.set("Connection failed")
            self.monitor_status_label.configure(text_color=color("error"))
            return
        self._monitor_serial = connection
        self._monitor_port = port
        self._monitor_stop = threading.Event()
        self._monitor_thread = threading.Thread(
            target=self._monitor_worker,
            args=(connection, self._monitor_stop, port),
            daemon=True,
        )
        self._monitor_thread.start()
        self.monitor_status_var.set(f"Connected to {port}")
        self.monitor_status_label.configure(text_color=color("success"))
        self.monitor_connect_button.configure(
            text="Disconnect",
            image=self._action_icons["unplug"],
            fg_color=color("error"),
            hover_color=color("error"),
            text_color=color("accent_text"),
        )
        self.monitor_send_button.configure(state="normal")
        self.command_entry.configure(state="normal")
        self.monitor_baud_menu.configure(state="disabled")
        self.scan_button.configure(state="disabled")
        self._write_monitor_log(f"Connected to {port} at {self.monitor_baud_var.get()} baud.\n")

    def _monitor_worker(self, connection: serial.Serial, stop_event: threading.Event, port: str) -> None:
        """Read serial data in the background and pass decoded output to Tk."""
        while not stop_event.is_set():
            try:
                data = serial_monitor.read(connection)
            except (serial.SerialException, OSError) as error:
                if not stop_event.is_set():
                    self._event_queue.put(("monitor-error", f"{port}\t{error}"))
                break
            if data and not stop_event.is_set():
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
        self.monitor_status_label.configure(text_color=color("text_muted"))
        self.monitor_connect_button.configure(
            text="Connect",
            image=self._action_icons["plug"],
            fg_color=color("accent"),
            hover_color=color("accent_hover"),
            text_color=color("accent_text"),
        )
        self.monitor_send_button.configure(state="disabled")
        self.command_entry.configure(state="disabled")
        self.monitor_baud_menu.configure(state="disabled" if self._flash_busy else "normal")
        if not self._flash_busy and not self._scan_active:
            self.scan_button.configure(state="normal")
        if not self._closing:
            self._write_monitor_log("Disconnected.\n")

    def send_monitor_input(self, _event: object | None = None) -> str | None:
        """Send monitor input exactly as written without appending line endings."""
        connection = self._monitor_serial
        message = self.monitor_input_var.get()
        if connection is None:
            self._write_monitor_log("Connect the monitor before sending data.\n")
            return "break" if _event is not None else None
        try:
            serial_monitor.send(connection, message)
        except (serial.SerialException, OSError) as error:
            LOGGER.error("Could not send monitor data: %s", error)
            self._write_monitor_log(f"Send failed: {error}\n")
            self.disconnect_monitor()
        else:
            self.monitor_input_var.set("")
        return "break" if _event is not None else None

    def clear_monitor_log(self) -> None:
        """Clear all retained serial-monitor output."""
        self._clear_text_widget(self.monitor_console)

    def save_monitor_log(self) -> None:
        """Save retained serial-monitor output to a user-selected text file."""
        destination = filedialog.asksaveasfilename(
            initialfile="esp_monitor.log",
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
        if self._scan_active or self._flash_busy or self._closing:
            return
        if self._monitor_serial is not None:
            self._write_monitor_log("Disconnect the monitor before rescanning devices.\n")
            self.device_status_var.set("Disconnect Monitor to rescan")
            self.device_status_label.configure(text_color=color("warning"))
            return
        self._scan_active = True
        self.device_status_var.set("Scanning for ESP devices…")
        self.device_status_label.configure(text_color=color("accent"))
        self._set_scan_controls(True)
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        """Handshake each serial port and return ESP devices with their MAC addresses."""
        try:
            devices = discover_devices()
        except OSError as error:
            LOGGER.error("Serial device scan failed: %s", error)
            self._event_queue.put(("scan-error", str(error)))
            return
        self._event_queue.put(
            ("devices", "\n".join("\t".join((device.chip_type, device.port, device.mac_address)) for device in devices))
        )

    def _set_scan_controls(self, scanning: bool) -> None:
        """Prevent serial operations from racing with the discovery handshake."""
        state = "disabled" if scanning or self._flash_busy else "normal"
        self.scan_button.configure(
            state="disabled" if scanning or self._flash_busy or self._monitor_serial is not None else "normal"
        )
        self.port_menu.configure(state="disabled" if scanning or self._flash_busy else "normal")
        self.flash_button.configure(state="disabled" if scanning or self._flash_busy else "normal")
        self.monitor_connect_button.configure(
            state="disabled" if scanning or self._flash_busy else "normal"
        )
        self.monitor_baud_menu.configure(
            state="disabled" if scanning or self._flash_busy or self._monitor_serial is not None else "normal"
        )
        self.baud_menu.configure(state=state)

    def flash_program(self) -> None:
        """Validate the configuration and start the selected esptool operation."""
        if self._closing:
            return
        if self._scan_active:
            self._write_console("Wait for device discovery to finish before flashing.\n")
            return
        if self._flash_busy:
            self._write_console("A flash operation is already running.\n")
            return
        port = self._selected_port()
        if not port:
            self._set_flash_status("Failed")
            self._write_console("Select a serial device before flashing.\n")
            return
        if self._monitor_serial is not None:
            if self._monitor_port == port:
                self._show_monitor_warning()
            else:
                self._write_console("Disconnect the active serial monitor before flashing another device.\n")
            return
        try:
            arguments = build_flash_arguments(
                port,
                self.baud_var.get(),
                [(partition.file_path.get(), partition.address.get()) for partition in self._partitions],
            )
        except ValueError as error:
            self._set_flash_status("Failed")
            self._write_console(f"{error}\n")
            return
        self._flash_busy = True
        self._flash_abort_requested.clear()
        self.progress_var.set(0)
        self.progress_text_var.set("Working…")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.flash_progress_area.grid()
        self._set_flash_status("Starting")
        self._set_scan_controls(False)
        self._refresh_partition_controls()
        self.monitor_connect_button.configure(state="disabled")
        self._set_abort_disabled()
        self._write_console(f"$ {' '.join(esptool_worker_command(arguments))}\n")
        self._flash_thread = threading.Thread(target=self._flash_worker, args=(arguments,), daemon=True)
        try:
            self._flash_thread.start()
        except RuntimeError as error:
            LOGGER.error("Could not start flash worker: %s", error)
            self.progress.stop()
            self._set_flash_busy(False)
            self._set_flash_status("Failed")
            self.progress_text_var.set("Failed")
            self._write_console(f"Unable to start flash operation: {error}\n")

    def _show_monitor_warning(self) -> None:
        """Ask whether to disconnect the selected monitored device before flashing."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Monitor Connected")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.configure(fg_color=color("window"))
        dialog.grab_set()
        ctk.CTkLabel(
            dialog,
            text="The selected device is connected to Monitor.\nDisconnect it before starting the flash operation?",
            justify="center",
            text_color=color("text"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
        ).pack(padx=28, pady=(24, 18))
        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.pack(padx=20, pady=(0, 20))
        ctk.CTkButton(
            actions,
            text="Disconnect and Proceed",
            command=lambda: self._disconnect_and_flash(dialog),
            fg_color=color("accent"),
            hover_color=color("accent_hover"),
            text_color=color("accent_text"),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            actions,
            text="Cancel",
            command=dialog.destroy,
            fg_color="transparent",
            border_width=1,
            border_color=color("border"),
            text_color=color("text_secondary"),
        ).pack(
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
            def forward_output(line: str) -> None:
                self._event_queue.put(("console", line))
                percentage = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
                if percentage is not None:
                    self._event_queue.put(("progress", percentage.group(1)))

            exit_code = self._flash_runner.run(
                arguments,
                forward_output,
                on_started=lambda: self._event_queue.put(("started", "")),
            )
            result = "aborted" if self._flash_abort_requested.is_set() and exit_code != 0 else str(exit_code)
            self._event_queue.put(("complete", result))
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            LOGGER.error("Could not start esptool: %s", error)
            self._event_queue.put(("console", f"Unable to start esptool: {error}\n"))
            self._event_queue.put(("complete", "startup-error"))

    def abort_flash(self) -> None:
        """Terminate the active esptool process, if a flash is underway."""
        if not self._flash_runner.terminate():
            self._write_console("No active flash operation to abort.\n")
            self._set_abort_disabled()
            return
        self._flash_abort_requested.set()
        self._set_flash_status("Aborting")
        self._set_abort_disabled()
        self._write_console("Abort requested.\n")

    def _set_abort_disabled(self) -> None:
        """Dim and disable Abort whenever no flash process can be terminated."""
        self.abort_button.configure(state="disabled", fg_color="transparent", hover_color=color("accent_subtle"))

    def _set_flash_busy(self, busy: bool) -> None:
        """Disable device and firmware controls while esptool owns the serial port."""
        self._flash_busy = busy
        self._set_scan_controls(self._scan_active)
        self._refresh_partition_controls()
        self.monitor_connect_button.configure(state="disabled" if busy or self._scan_active else "normal")
        self.monitor_baud_menu.configure(
            state="disabled" if busy or self._scan_active or self._monitor_serial is not None else "normal"
        )
        if not busy:
            self._set_abort_disabled()

    def toggle_log(self) -> None:
        """Expand the flash output within its own layout without resizing the window."""
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.console.grid()
            self.flash_workspace.configure(height=220)
            self.flash_workspace.grid_propagate(False)
            self.flash_view.grid_rowconfigure(1, weight=0)
            self.flash_view.grid_rowconfigure(3, weight=1)
            self.log_toggle.configure(image=self._icons["chevron-down"])
            self.log_tooltip.text = "Hide flash output"
        else:
            self.console.grid_remove()
            self.flash_workspace.grid_propagate(True)
            self.flash_view.grid_rowconfigure(1, weight=1)
            self.flash_view.grid_rowconfigure(3, weight=0)
            self.log_toggle.configure(image=self._icons["chevron-up"])
            self.log_tooltip.text = "Show flash output"
        self._settings.show_flash_logs = self.log_visible

    def clear_log(self) -> None:
        """Remove all retained output from the expanded console."""
        self._clear_text_widget(self.console)

    def save_log(self) -> None:
        """Save retained console output to a user-selected text file."""
        destination = filedialog.asksaveasfilename(
            initialfile="esp_flash.log",
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
        console_messages: list[str] = []
        monitor_messages: list[str] = []
        processed = 0
        while processed < EVENT_BATCH_SIZE:
            try:
                event, value = self._event_queue.get_nowait()
            except queue.Empty:
                break
            processed += 1
            if event == "console":
                console_messages.append(value)
            elif event == "monitor":
                monitor_messages.append(value)
            elif event == "monitor-error":
                port, _, error = value.partition("\t")
                if port == self._monitor_port:
                    monitor_messages.append(f"Monitor connection lost: {error}\n")
                    self.disconnect_monitor()
                    self.monitor_status_var.set("Connection lost")
                    self.monitor_status_label.configure(text_color=color("error"))
            elif event == "devices":
                devices = [device.split("\t") for device in value.splitlines()]
                self._display_devices(devices)
                self._scan_active = False
                self._set_scan_controls(False)
                count = len(devices)
                self.device_status_var.set(
                    f"{count} ESP device found" if count == 1 else f"{count} ESP devices found"
                )
                self.device_status_label.configure(
                    text_color=color("success") if count else color("text_muted")
                )
                console_messages.append(f"Scan complete: {count} ESP device(s) found.\n")
            elif event == "scan-error":
                self._scan_active = False
                self._display_devices([])
                self._set_scan_controls(False)
                self.device_status_var.set("Device scan failed")
                self.device_status_label.configure(text_color=color("error"))
                console_messages.append(f"Device scan failed: {value}\n")
            elif event == "started":
                if self._flash_busy and not self._flash_abort_requested.is_set():
                    self._set_flash_status("Flashing")
                    self.abort_button.configure(state="normal")
            elif event == "complete":
                self._set_flash_busy(False)
                self._set_abort_disabled()
                self.progress.stop()
                if value == "0":
                    self._set_flash_status("Flashed")
                    self.progress_text_var.set("Complete")
                    console_messages.append("Flash completed successfully.\n")
                elif value == "aborted":
                    self._set_flash_status("Aborted")
                    self.progress_text_var.set("Aborted")
                    console_messages.append("Flash operation aborted.\n")
                else:
                    self._set_flash_status("Failed")
                    self.progress_text_var.set("Failed")
                    console_messages.append(f"Flash failed with status: {value}\n")
            elif event == "progress":
                percentage = min(max(float(value), 0), 100)
                if self.status_var.get() != "Aborting":
                    self.progress.stop()
                    self.progress.configure(mode="determinate")
                self.progress_var.set(percentage / 100)
                self.progress_text_var.set(f"{percentage:.0f}%")
                if self.status_var.get() != "Aborting":
                    self._set_flash_status("Flashing")
        if console_messages:
            self._write_console("".join(console_messages))
        if monitor_messages:
            self._write_monitor_log("".join(monitor_messages))
        if not self._closing:
            delay = 20 if processed == EVENT_BATCH_SIZE or not self._event_queue.empty() else 60
            self._event_after_id = self.after(delay, self._drain_events)

    def _display_devices(self, devices: list[list[str]]) -> None:
        """Populate compact device entries containing chip type, COM ID, and MAC."""
        entries = [f"{chip_type} | {port} | {mac_address}" for chip_type, port, mac_address in devices]
        self.port_menu.configure(values=entries or ["No device selected"])
        self.port_var.set(entries[0] if entries else "No device selected")

    def _write_console(self, message: str) -> None:
        """Append text to the read-only console and reveal its latest output."""
        self._append_text(self.console, message)

    def _write_monitor_log(self, message: str) -> None:
        """Append text to the read-only serial monitor and reveal its latest output."""
        self._append_text(self.monitor_console, message)

    @staticmethod
    def _clear_text_widget(widget: ctk.CTkTextbox) -> None:
        """Clear a read-only text widget while keeping it non-editable."""
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.configure(state="disabled")

    @staticmethod
    def _append_text(widget: ctk.CTkTextbox, message: str) -> None:
        """Append a batch of output, retain a bounded history, and respect scroll position."""
        following_output = widget.yview()[1] >= 0.98
        widget.configure(state="normal")
        widget.insert("end", message)
        line_count = int(widget.index("end-1c").split(".", maxsplit=1)[0])
        if line_count > MAX_CONSOLE_LINES:
            widget.delete("1.0", f"{line_count - MAX_CONSOLE_LINES + 1}.0")
        widget.delete("1.0", f"end-{MAX_CONSOLE_CHARS}c")
        if following_output:
            widget.see("end")
        widget.configure(state="disabled")

    def close_application(self) -> None:
        """Close active device resources before destroying the main window."""
        if self._closing:
            return
        self._closing = True
        if self._event_after_id is not None:
            try:
                self.after_cancel(self._event_after_id)
            except TclError:
                LOGGER.debug("The event poll had already completed during shutdown")
            self._event_after_id = None
        if self.state() == "normal":
            width, height = self.winfo_width(), self.winfo_height()
            if width >= 900 and height >= 600:
                self._settings.window_size = (width, height)
        if self._monitor_serial is not None:
            self.disconnect_monitor()
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=0.35)
        if self._flash_runner.terminate():
            self._flash_abort_requested.set()
        if self._flash_thread is not None and self._flash_thread.is_alive():
            self._flash_thread.join(timeout=1.0)
        self.destroy()