"""Small helpers shared by the UI widgets."""

import logging
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from types import TracebackType

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget

from labcollector.core.report import COLORS
from labcollector.records import CollectionStatus

STATUS_NAMES = {
    CollectionStatus.SUCCESS: "Success",
    CollectionStatus.PARTIAL: "Partial",
    CollectionStatus.FAILED: "Failed",
}

# The same colors as the HTML report, so a status looks the same everywhere.
WARNING_COLOR = QColor(COLORS[CollectionStatus.PARTIAL][1])  # orange: needs attention
ERROR_COLOR = QColor(COLORS[CollectionStatus.FAILED][1])  # red: a problem
SUCCESS_COLOR = QColor(COLORS[CollectionStatus.SUCCESS][1])  # green: done


def format_date(iso_text: str) -> str:
    """'2026-11-16T11:13:09' -> '16 Nov 2026, 11:13'."""
    try:
        return datetime.fromisoformat(iso_text).strftime("%d %b %Y, %H:%M")
    except ValueError:
        return iso_text


def status_color(status: CollectionStatus) -> QColor:
    """The text color used for a status, the same as in the HTML report."""
    _background, text = COLORS[status]
    return QColor(text)


def open_path(path: Path, parent: QWidget | None = None) -> None:
    """Open a file with its default program (e.g. .xlsx in Excel), or a folder in Explorer."""
    if _exists_or_warn(path, parent):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def show_in_folder(path: Path, parent: QWidget | None = None) -> None:
    """Open Explorer at the file's folder with the file selected."""
    if not _exists_or_warn(path, parent):
        return
    if sys.platform == "win32":
        subprocess.Popen(f'explorer /select,"{path}"')
    else:
        open_path(path.parent, parent)


def _exists_or_warn(path: Path, parent: QWidget | None) -> bool:
    if path.exists():
        return True
    QMessageBox.warning(parent, "Not found", f"This no longer exists (moved or deleted):\n{path}")
    return False


def install_error_handler(log_file: Path) -> None:
    """Catch any error nothing else handled: log it in full and tell the user.

    Without this, an unexpected error inside a button's code is only printed to a console the
    user never sees (there is none in the .exe), and the app just seems to do nothing.
    """

    def handle(
        error_type: type[BaseException], error: BaseException, trace: TracebackType | None
    ) -> None:
        if issubclass(error_type, KeyboardInterrupt):  # Ctrl+C in a terminal: behave normally
            sys.__excepthook__(error_type, error, trace)
            return
        logging.getLogger("labcollector").critical(
            "Unexpected error", exc_info=(error_type, error, trace)
        )
        if threading.current_thread() is not threading.main_thread():
            return  # Qt allows windows only on the main thread; the error is logged above
        QMessageBox.critical(
            None,
            "Unexpected error",
            f"Something went wrong: {error}\n\nThe details were written to the log file:\n"
            f"{log_file}",
        )

    sys.excepthook = handle
