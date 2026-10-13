"""Focused CustomTkinter widget extensions used by the application."""

from __future__ import annotations

from typing import Any
from tkinter import TclError

import customtkinter as ctk
from PIL import ImageTk

from espress_view.gui.icons import load_icon


class ChevronOptionMenu(ctk.CTkOptionMenu):
    """Keep CTkOptionMenu behavior while drawing a Lucide chevron in its arrow slot."""

    # CustomTkinter supplies these framework ancestors.
    # pylint: disable=too-many-ancestors
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._chevron_image: ImageTk.PhotoImage | None = None
        self._draw()

    def _draw(self, no_color_updates: bool = False) -> None:
        # Drawing the inherited widget requires keeping geometry and state together.
        # pylint: disable=too-many-locals
        super()._draw(no_color_updates)
        if not hasattr(self, "_chevron_image"):
            return

        canvas = self._canvas
        size = self._apply_widget_scaling(14)
        height = self._apply_widget_scaling(self._current_height)
        width = self._apply_widget_scaling(self._current_width)
        text_color = (
            self.cget("text_color_disabled")
            if self.cget("state") == "disabled"
            else self.cget("text_color")
        )
        try:
            foreground_rgb = self.winfo_rgb(self._apply_appearance_mode(text_color))
            foreground = (
                f"#{foreground_rgb[0] >> 8:02x}"
                f"{foreground_rgb[1] >> 8:02x}"
                f"{foreground_rgb[2] >> 8:02x}"
            )
        except (TclError, ValueError):
            foreground = "#66707D"
        image = load_icon("chevron-down", foreground, (max(1, round(size)),) * 2)
        self._chevron_image = ImageTk.PhotoImage(image)
        center_x, center_y = width - (height / 2), height / 2
        tag = "lucide_dropdown_chevron"
        background = self._apply_appearance_mode(self.cget("button_color"))
        if not canvas.find_withtag(tag):
            canvas.create_rectangle(
                center_x - size / 2,
                center_y - size / 2,
                center_x + size / 2,
                center_y + size / 2,
                fill=background,
                outline=background,
                tags=(tag,),
            )
            canvas.create_image(center_x, center_y, image=self._chevron_image, tags=(tag,))
            canvas.tag_bind(tag, "<Enter>", self._on_chevron_enter)
            canvas.tag_bind(tag, "<Leave>", self._on_chevron_leave)
        else:
            items = canvas.find_withtag(tag)
            if len(items) >= 2:
                rectangle_id, image_id = items[0], items[1]
                canvas.coords(
                    rectangle_id,
                    center_x - size / 2,
                    center_y - size / 2,
                    center_x + size / 2,
                    center_y + size / 2,
                )
                canvas.coords(image_id, center_x, center_y)
                canvas.itemconfigure(rectangle_id, fill=background, outline=background)
                canvas.itemconfigure(image_id, image=self._chevron_image)

    def _on_chevron_enter(self, event: object = 0) -> None:
        if self._hover and self._state == "normal" and self._values:
            items = self._canvas.find_withtag("lucide_dropdown_chevron")
            if items:
                self._canvas.itemconfigure(
                    items[0],
                    fill=self._apply_appearance_mode(self.cget("button_hover_color")),
                    outline=self._apply_appearance_mode(self.cget("button_hover_color")),
                )
            self._on_enter(event)

    def _on_chevron_leave(self, event: object = 0) -> None:
        items = self._canvas.find_withtag("lucide_dropdown_chevron")
        if items:
            background = self._apply_appearance_mode(self.cget("button_color"))
            self._canvas.itemconfigure(
                items[0],
                fill=background,
                outline=background,
            )
        self._on_leave(event)
