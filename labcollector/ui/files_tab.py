"""The Files tab: every collected file, grouped by collection and then by category.

Double-click a file to open it with its default program; right-click for more.
"""

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMenu, QStackedWidget, QTreeWidget, QTreeWidgetItem, QWidget

from labcollector.core.report import PROBLEM_LABELS, human_size
from labcollector.records import Collection, FileResult, FileStatus
from labcollector.ui.helpers import (
    ERROR_COLOR,
    STATUS_NAMES,
    format_date,
    open_path,
    show_in_folder,
    status_color,
)

PATH_ROLE = Qt.ItemDataRole.UserRole  # where each tree row keeps its file or folder path
EMPTY_PAGE, LIST_PAGE = 0, 1


class FilesTab(QStackedWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Size", "Status", "Source / rule"])
        self.tree.setColumnWidth(0, 300)  # name
        self.tree.setColumnWidth(1, 90)  # size
        self.tree.setColumnWidth(2, 170)  # status, wide enough for "Corrupt or unreadable"
        self.tree.itemDoubleClicked.connect(self._open_item)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_menu)

        empty = QLabel("No files yet. Click “Collect now” to collect this run's files.")
        empty.setObjectName("muted")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.addWidget(empty)  # EMPTY_PAGE
        self.addWidget(self.tree)  # LIST_PAGE

    def show_collections(self, collections: list[Collection]) -> None:
        """Newest collection first and expanded; older ones collapsed."""
        self.tree.clear()
        for collection in collections:
            self.tree.addTopLevelItem(_collection_item(collection))
        if collections:  # items can only be expanded once they're in the tree
            newest = self.tree.topLevelItem(0)
            newest.setExpanded(True)
            for index in range(newest.childCount()):
                newest.child(index).setExpanded(True)
        self.setCurrentIndex(LIST_PAGE if collections else EMPTY_PAGE)

    def _open_item(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, PATH_ROLE)
        if path and item.childCount() == 0:  # a file (folders just expand on double-click)
            open_path(Path(path), self)

    def _show_menu(self, position: QPoint) -> None:
        item = self.tree.itemAt(position)
        path = item.data(0, PATH_ROLE) if item else None
        if not path:
            return
        menu = QMenu(self)
        menu.addAction("Open", lambda: open_path(Path(path), self))
        menu.addAction("Show in folder", lambda: show_in_folder(Path(path), self))
        menu.addAction("Copy path", lambda: QGuiApplication.clipboard().setText(path))
        menu.exec(self.tree.viewport().mapToGlobal(position))


def _collection_item(collection: Collection) -> QTreeWidgetItem:
    """collection (date, status) -> category folders -> files."""
    files = [f for f in collection.files if f.dest_path]  # only files that were copied
    item = QTreeWidgetItem(
        [
            format_date(collection.started_at),
            "",
            STATUS_NAMES[collection.status],
            f"{len(files)} files",
        ]
    )
    item.setForeground(2, status_color(collection.status))
    item.setData(0, PATH_ROLE, collection.folder)

    for category in sorted({f.category for f in files}):
        in_category = [f for f in files if f.category == category]
        folder = QTreeWidgetItem([f"{category}  ({len(in_category)})"])
        folder.setData(0, PATH_ROLE, str(Path(collection.folder) / category))
        for file in in_category:
            folder.addChild(_file_item(file))
        item.addChild(folder)
    return item


def _file_item(file: FileResult) -> QTreeWidgetItem:
    copied = file.status == FileStatus.COPIED
    status = "Verified" if copied else PROBLEM_LABELS[file.status]
    source = f"{file.source} / {file.rule}"
    item = QTreeWidgetItem([Path(file.dest_path).name, human_size(file.size), status, source])
    item.setData(0, PATH_ROLE, file.dest_path)
    if not copied:  # e.g. a corrupt file: it was copied, so it's listed, but marked red
        item.setToolTip(2, file.error)
        item.setForeground(2, ERROR_COLOR)
    return item
