"""Entry point: ``python -m labcollector``."""

import logging
import sys

from labcollector import paths
from labcollector.logging_setup import setup_logging


def main() -> int:
    setup_logging(paths.LOG_DIR)
    logging.getLogger(__name__).info("Lab Collector starting (data folder: %s)", paths.DATA_DIR)
    # The main window is added in milestone M3.
    print("Lab Collector: the user interface is not built yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
