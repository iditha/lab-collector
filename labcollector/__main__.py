"""Entry point: ``python -m labcollector``."""

import logging
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from labcollector import paths
from labcollector.infra.repository import Repository
from labcollector.logging_setup import setup_logging
from labcollector.services.run_service import RunService
from labcollector.ui.main_window import MainWindow


def main() -> int:
    setup_logging(paths.LOG_DIR)
    logging.getLogger(__name__).info("Lab Collector starting (data folder: %s)", paths.DATA_DIR)

    app = QApplication(sys.argv)
    app.setApplicationName("Lab Collector")
    app.setStyle("Fusion")  # same look on every Windows version, and a good base for the QSS
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet((paths.RESOURCE_DIR / "ui" / "style.qss").read_text(encoding="utf-8"))

    # Build the app's objects once, here, and pass them in (dependency injection).
    repository = Repository(paths.DB_PATH)
    window = MainWindow(RunService(repository))
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
