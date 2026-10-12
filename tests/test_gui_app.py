"""Tests for GUI lifecycle events and editable log export defaults."""

import queue
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

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


if __name__ == "__main__":
    unittest.main()
