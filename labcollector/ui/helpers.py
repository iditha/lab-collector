"""Small helpers shared by the UI widgets."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

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
