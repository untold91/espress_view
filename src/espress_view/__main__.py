"""Application and esptool-worker entry point."""

import logging
import sys

from espress_view.flasher.runner import run_esptool_worker
from espress_view.utils.instance import acquire_single_instance, release_single_instance

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Configure logging and run the Espress View application."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not acquire_single_instance():
        LOGGER.warning("Espress View is already running")
        return
    from espress_view.gui.app import EspressView  # pylint: disable=import-outside-toplevel

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
