"""Appearance mode selector segmented control."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from espress_view.gui.design import color


class AppearanceSelector(ctk.CTkFrame):
    """Segmented icon selector for Light, System, and Dark appearance modes."""

    # CustomTkinter contributes framework ancestors and the selector injects three callbacks.
    # pylint: disable=too-many-ancestors
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        theme_var: ctk.StringVar,
        icons: dict[str, ctk.CTkImage],
        on_change: Callable[[str], None],
        add_tooltip: Callable[[ctk.CTkBaseClass, str], None],
        add_focus_indicator: Callable[[ctk.CTkBaseClass], None],
        **kwargs: object,
    ) -> None:
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        super().__init__(
            master,
            fg_color=color("surface"),
            corner_radius=8,
            border_width=1,
            border_color=color("border"),
            **kwargs,
        )
        self.theme_var = theme_var
        self.on_change = on_change
        self.buttons: dict[str, ctk.CTkButton] = {}

        for column, (mode, icon_name) in enumerate(
            (("light", "sun"), ("system", "monitor"), ("dark", "moon"))
        ):
            self.grid_columnconfigure(column, weight=1, uniform="appearance")
            button = ctk.CTkButton(
                self,
                text="",
                image=icons[icon_name],
                command=lambda selected=mode: self._handle_click(selected),
                width=44,
                height=38,
                corner_radius=6,
                fg_color="transparent",
                hover_color=color("accent_subtle"),
                text_color=color("text_secondary"),
            )
            button.appearance_accessible_name = f"{mode.title()} appearance"
            button.grid(row=0, column=column, sticky="ew", padx=2, pady=2)
            self.buttons[mode] = button
            add_tooltip(button, f"{mode.title()} appearance")
            add_focus_indicator(button)

        self.sync()

    def _handle_click(self, mode: str) -> None:
        self.on_change(mode)
        self.sync()

    def sync(self) -> None:
        """Keep exactly one appearance segment highlighted."""
        selected = self.theme_var.get()
        for mode, button in self.buttons.items():
            active = mode == selected
            button.configure(
                fg_color=color("accent_subtle") if active else "transparent",
                text_color=color("accent") if active else color("text_secondary"),
            )
