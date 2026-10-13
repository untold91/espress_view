"""Tests for GUI lifecycle events and editable log export defaults."""

# Test names are descriptive, and GUI tests intentionally inspect widget internals.
# pylint: disable=duplicate-code,missing-class-docstring,missing-function-docstring,protected-access,wrong-import-position

import queue
import sys
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from espress_view.gui.app import EspressView


class GuiLogExportTests(unittest.TestCase):
    def test_monitor_export_uses_an_editable_default_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "custom-monitor.log"
            subject = Mock()
            subject.monitor_console.get.return_value = "serial output\n"

            with patch(
                "espress_view.gui.app.filedialog.asksaveasfilename",
                return_value=str(destination),
            ) as save_dialog:
                EspressView.save_monitor_log(subject)

            save_dialog.assert_called_once_with(
                initialfile="esp_monitor.log",
                defaultextension=".log",
                filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
            )
            self.assertEqual(destination.read_text(encoding="utf-8"), "serial output\n")

    def test_flash_export_uses_an_editable_default_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "custom-flash.log"
            subject = Mock()
            subject.console.get.return_value = "flash output\n"

            with patch(
                "espress_view.gui.app.filedialog.asksaveasfilename",
                return_value=str(destination),
            ) as save_dialog:
                EspressView.save_log(subject)

            save_dialog.assert_called_once_with(
                initialfile="esp_flash.log",
                defaultextension=".log",
                filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
            )
            self.assertEqual(destination.read_text(encoding="utf-8"), "flash output\n")


class FlashUiLifecycleTests(unittest.TestCase):
    @staticmethod
    def _subject() -> Mock:
        subject = Mock()
        subject._event_queue = queue.Queue()
        subject._closing = True
        subject._flash_busy = True
        subject._flash_abort_requested = Event()
        return subject

    def test_abort_remains_aborting_until_the_completion_event(self) -> None:
        subject = self._subject()
        subject._flash_runner.terminate.return_value = True

        EspressView.abort_flash(subject)

        self.assertTrue(subject._flash_abort_requested.is_set())
        subject._set_flash_status.assert_called_once_with("Aborting")

        subject._event_queue.put(("complete", "aborted"))
        EspressView._drain_events(subject)

        subject._set_flash_status.assert_called_with("Aborted")
        self.assertEqual(subject._set_abort_disabled.call_count, 2)

    def test_child_start_event_enables_abort_and_sets_flashing_state(self) -> None:
        subject = self._subject()
        subject._event_queue.put(("started", ""))

        EspressView._drain_events(subject)

        subject._set_flash_status.assert_called_once_with("Flashing")
        subject.abort_button.configure.assert_called_once_with(state="normal")

    def test_success_and_failure_completion_use_backend_outcomes(self) -> None:
        for outcome, expected_status in (("0", "Flashed"), ("2", "Failed")):
            with self.subTest(outcome=outcome):
                subject = self._subject()
                subject._event_queue.put(("complete", outcome))

                EspressView._drain_events(subject)

                subject._set_flash_status.assert_called_once_with(expected_status)
                subject._set_flash_busy.assert_called_once_with(False)
                subject.progress.stop.assert_called_once_with()
                subject.progress_var.set.assert_not_called()

    def test_percentage_events_switch_to_real_determinate_progress(self) -> None:
        subject = self._subject()
        subject.status_var.get.return_value = "Flashing"
        subject._event_queue.put(("progress", "37.5"))

        EspressView._drain_events(subject)

        subject.progress.stop.assert_called_once_with()
        subject.progress.configure.assert_called_once_with(mode="determinate")
        subject.progress_var.set.assert_called_once_with(0.375)
        subject._set_flash_status.assert_called_once_with("Flashing")


class LayoutAndControlsTests(unittest.TestCase):
    def test_toggle_log_expands_and_collapses_responsively(self) -> None:
        subject = Mock()
        subject.log_visible = False
        subject.console = Mock()
        subject.flash_workspace = Mock()
        subject.flash_view = Mock()
        subject.log_toggle = Mock()
        subject.log_tooltip = Mock()
        subject._icons = {"chevron-down": Mock(), "chevron-up": Mock()}
        subject._settings = Mock()

        # Expanding
        EspressView.toggle_log(subject)
        self.assertTrue(subject.log_visible)
        subject.console.grid.assert_called_once()
        subject.flash_workspace.grid_propagate.assert_called_once_with(True)
        subject.flash_view.grid_rowconfigure.assert_any_call(1, weight=1, minsize=140)
        subject.flash_view.grid_rowconfigure.assert_any_call(3, weight=1, minsize=120)

        # Collapsing
        EspressView.toggle_log(subject)
        self.assertFalse(subject.log_visible)
        subject.console.grid_remove.assert_called_once()
        subject.flash_view.grid_rowconfigure.assert_any_call(1, weight=1, minsize=0)
        subject.flash_view.grid_rowconfigure.assert_any_call(3, weight=0, minsize=0)

    def test_remove_partition_renumbers_remaining_partitions(self) -> None:
        subject = Mock()
        subject._flash_busy = False
        partition0 = Mock()
        partition1 = Mock()
        partition2 = Mock()
        subject._partitions = [partition0, partition1, partition2]

        EspressView.remove_partition(subject, partition1)

        self.assertEqual(subject._partitions, [partition0, partition2])
        partition1.row.destroy.assert_called_once()
        # Remaining partition renumbered:
        partition0.row.grid_configure.assert_called_with(row=0)
        partition0.index_label.configure.assert_called_with(text="01")
        partition2.row.grid_configure.assert_called_with(row=1)
        partition2.index_label.configure.assert_called_with(text="02")

    def test_cannot_remove_first_partition_or_during_flash(self) -> None:
        subject = Mock()
        subject._flash_busy = True
        partition0 = Mock()
        subject._partitions = [partition0]

        # Cannot remove while flash busy
        EspressView.remove_partition(subject, partition0)
        partition0.row.destroy.assert_not_called()

        subject._flash_busy = False
        # Cannot remove partition 0 (permanent row)
        EspressView.remove_partition(subject, partition0)
        partition0.row.destroy.assert_not_called()

    def test_change_theme_validates_mode(self) -> None:
        subject = Mock()
        subject._settings = Mock()
        subject.theme_var = Mock()
        subject._sync_appearance_selector = Mock()

        with patch("customtkinter.set_appearance_mode") as set_mode:
            EspressView._change_theme(subject, "dark")
            set_mode.assert_called_once_with("Dark")
            self.assertEqual(subject._settings.theme, "dark")

        with self.assertRaises(ValueError):
            EspressView._change_theme(subject, "invalid-theme")


if __name__ == "__main__":
    unittest.main()
