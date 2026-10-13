"""Run esptool in a child process so its output can be monitored and stopped."""

import subprocess
import sys
import threading
from collections.abc import Callable


def esptool_worker_command(arguments: list[str]) -> list[str]:
    """Build a command that runs the bundled esptool worker in any launch mode."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--esptool-worker", *arguments]
    return [sys.executable, "-m", "espress_view", "--esptool-worker", *arguments]


class FlashRunner:
    """Own the esptool subprocess and expose its output and abort operation."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        """Report whether an esptool process is currently running."""
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def run(
        self,
        arguments: list[str],
        on_output: Callable[[str], None],
        on_started: Callable[[], None] | None = None,
    ) -> int:
        """Run esptool, forward each output line, and return its exit code."""
        with subprocess.Popen(
            esptool_worker_command(arguments),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as process:
            with self._lock:
                self._process = process
            try:
                if on_started is not None:
                    on_started()
                if process.stdout is not None:
                    for line in process.stdout:
                        on_output(line)
                return process.wait()
            finally:
                with self._lock:
                    if self._process is process:
                        self._process = None

    def terminate(self) -> bool:
        """Terminate the active subprocess; return whether termination was requested."""
        with self._lock:
            process = self._process
            if process is None or process.poll() is not None:
                return False
            process.terminate()
            return True


def run_esptool_worker(arguments: list[str]) -> int:
    """Run esptool inside the current Python or packaged executable process."""
    import esptool  # pylint: disable=import-outside-toplevel
    from esptool.util import FatalError  # pylint: disable=import-outside-toplevel

    try:
        esptool.main(arguments)
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 1
    except FatalError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0
