"""Entry point: ``python -m labcollector``."""

import logging
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from labcollector import __version__, paths
from labcollector.infra.repository import Repository
from labcollector.logging_setup import setup_logging
from labcollector.services.collection_service import CollectionService
from labcollector.services.run_service import RunService
from labcollector.services.settings_service import SettingsService
from labcollector.ui.helpers import install_error_handler
from labcollector.ui.main_window import MainWindow


def main() -> int:
    log_file = setup_logging(paths.LOG_DIR)
    logging.getLogger(__name__).info(
        "Lab Collector %s starting (data folder: %s)", __version__, paths.DATA_DIR
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Lab Collector")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")  # same look on every Windows version, and a good base for the QSS
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet((paths.RESOURCE_DIR / "ui" / "style.qss").read_text(encoding="utf-8"))
    install_error_handler(log_file)

    # Build the app's objects once, here, and pass them in (dependency injection).
    repository = Repository(paths.DB_PATH)
    window = MainWindow(
        run_service=RunService(repository),
        collection_service=CollectionService(repository),
        settings_service=SettingsService(paths.CONFIG_PATH, paths.DEFAULT_OUTPUT_ROOT),
        user_guide=paths.USER_GUIDE,
    )
    window.show()
    window.load_config()  # a broken config.yaml is explained now, not at the first collection
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
