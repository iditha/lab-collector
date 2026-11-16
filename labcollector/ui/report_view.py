"""Shows a collection's report inside the app. Clicking a file name opens the file."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QTextBrowser, QWidget

from labcollector.core import report
from labcollector.records import Collection, Run
from labcollector.ui.helpers import open_path


class ReportView(QTextBrowser):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._folder = ""
        self.setOpenLinks(False)  # we open links ourselves, with the file's own program
        self.anchorClicked.connect(self._open_link)

    def show_collection(self, collection: Collection, run: Run) -> None:
        self._folder = collection.folder
        self.setHtml(report.to_html(collection, run))

    def _open_link(self, url: QUrl) -> None:
        # Report links are relative to the collection folder, e.g. "logs/syslog_1.txt".
        relative = url.path(QUrl.ComponentFormattingOption.FullyDecoded)
        open_path(Path(self._folder) / relative, self)
