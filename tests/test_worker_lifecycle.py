"""Tests for worker exception recovery, operation lifecycle, and stale event handling."""

# Test names are descriptive, and GUI tests intentionally inspect widget internals.
# pylint: disable=duplicate-code,missing-class-docstring,missing-function-docstring,protected-access,wrong-import-position

import queue
import sys
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from espress_view.gui.app import EspressView


class WorkerLifecycleAndRecoveryTests(unittest.TestCase):
    @staticmethod
    def _subject() -> Mock:
        subject = Mock()
        subject._event_queue = queue.Queue()
        subject._closing = True
        subject._flash_busy = True
        subject._flash_abort_requested = Event()
        subject._flash_op_id = 1
        subject._scan_op_id = 1
        subject._scan_active = True
        subject._partitions = []
        subject.baud_var = Mock(get=Mock(return_value="2000000"))
        return subject

    @patch("espress_view.gui.app.discover_devices", side_effect=RuntimeError("Hardware bus glitch"))
    def test_discovery_worker_recovers_from_unexpected_exception(self, _mock_discover: Mock) -> None:
        subject = self._subject()
        EspressView._scan_worker(subject, op_id=1)

        event, payload = subject._event_queue.get_nowait()
        self.assertEqual(event, "scan-error")
        self.assertIn("Scan failure: Hardware bus glitch", payload)

    @patch("espress_view.gui.app.discover_devices", side_effect=OSError("Serial port busy"))
    def test_discovery_worker_handles_os_error(self, _mock_discover: Mock) -> None:
        subject = self._subject()
        EspressView._scan_worker(subject, op_id=1)

        event, payload = subject._event_queue.get_nowait()
        self.assertEqual(event, "scan-error")
        self.assertIn("Serial port busy", payload)

    def test_flash_worker_handles_unexpected_runner_exception(self) -> None:
        subject = self._subject()
        subject._flash_runner.run.side_effect = RuntimeError("Process pipe exploded")

        EspressView._flash_worker(subject, ["--port", "COM3"], op_id=1)

        events = []
        while not subject._event_queue.empty():
            events.append(subject._event_queue.get_nowait())

        event_types = [evt[0] for evt in events]
        self.assertIn("console", event_types)
        self.assertIn("complete", event_types)
        complete_evt = next(e for e in events if e[0] == "complete")
        self.assertIn("worker-error", complete_evt[1])

    def test_drain_events_recovers_gui_on_worker_error(self) -> None:
        subject = self._subject()
        subject._event_queue.put(("complete", "1\tworker-error"))

        EspressView._drain_events(subject)

        subject._set_flash_busy.assert_called_once_with(False)
        subject._set_flash_status.assert_called_once_with("Failed")
        subject.progress.stop.assert_called_once()
        subject._set_abort_disabled.assert_called_once()

    def test_drain_events_recovers_gui_on_scan_error(self) -> None:
        subject = self._subject()
        subject._event_queue.put(("scan-error", "1\tDevice scan failed"))

        EspressView._drain_events(subject)

        self.assertFalse(subject._scan_active)
        subject._set_scan_controls.assert_called_once_with(False)
        subject.device_status_var.set.assert_called_once_with("Device scan failed")

    def test_stale_flash_events_are_ignored(self) -> None:
        subject = self._subject()
        subject._flash_op_id = 2  # Current op_id is 2

        # Event from older op_id 1
        subject._event_queue.put(("complete", "1\t0"))

        EspressView._drain_events(subject)

        # Should NOT trigger completion because op_id is stale
        subject._set_flash_status.assert_not_called()
        subject._set_flash_busy.assert_not_called()

    def test_current_flash_events_with_matching_op_id_are_processed(self) -> None:
        subject = self._subject()
        subject._flash_op_id = 2

        # Event with matching op_id 2
        subject._event_queue.put(("complete", "2\t0"))

        EspressView._drain_events(subject)

        subject._set_flash_status.assert_called_once_with("Flashed")
        subject._set_flash_busy.assert_called_once_with(False)

    def test_legacy_events_without_op_id_are_processed(self) -> None:
        subject = self._subject()
        subject._flash_op_id = 1

        # Legacy 2-element tuple without op_id
        subject._event_queue.put(("complete", "0"))

        EspressView._drain_events(subject)

        subject._set_flash_status.assert_called_once_with("Flashed")
        subject._set_flash_busy.assert_called_once_with(False)

    def test_abort_when_no_active_operation(self) -> None:
        subject = self._subject()
        subject._flash_runner.terminate.return_value = False

        EspressView.abort_flash(subject)

        subject._set_abort_disabled.assert_called_once()
        subject._set_flash_status.assert_not_called()
        self.assertFalse(subject._flash_abort_requested.is_set())

    @patch("espress_view.gui.app.build_flash_arguments", return_value=["--chip", "auto"])
    @patch("threading.Thread.start", side_effect=RuntimeError("Thread creation failed"))
    def test_flash_thread_start_failure_recovers_state(self, _thread_start: Mock, _build_args: Mock) -> None:
        subject = self._subject()
        subject._closing = False
        subject._scan_active = False
        subject._flash_busy = False
        subject._selected_port.return_value = "COM5"
        subject._monitor_serial = None
        subject._partitions = []
        subject.baud_var.get.return_value = "2000000"

        EspressView.flash_program(subject)

        subject.progress.stop.assert_called_once()
        subject._set_flash_busy.assert_called_once_with(False)
        subject._set_flash_status.assert_called_with("Failed")
        self.assertEqual(subject.progress_text_var.set.call_args[0][0], "Failed")


if __name__ == "__main__":
    unittest.main()
