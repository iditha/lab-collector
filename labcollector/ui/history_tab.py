"""The History tab: every collection of the run, newest first, with its report."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from labcollector.core.report import summary
from labcollector.records import Collection, Run
from labcollector.ui.helpers import STATUS_NAMES, format_date, open_path, status_color
from labcollector.ui.report_view import ReportView

COLUMNS = ["Collected on", "Status", "Files collected", "Problems"]
EMPTY_PAGE, LIST_PAGE = 0, 1


class HistoryTab(QStackedWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._run: Run | None = None
        self._collections: list[Collection] = []

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.currentCellChanged.connect(self._on_row_selected)

        self.report = ReportView()
        open_folder = QPushButton("Open collection folder")
        open_folder.clicked.connect(self._open_folder)

        report_area = QWidget()
        report_layout = QVBoxLayout(report_area)
        report_layout.setContentsMargins(0, 0, 0, 0)
        report_layout.addWidget(self.report)
        report_layout.addWidget(open_folder, alignment=Qt.AlignmentFlag.AlignRight)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(report_area)
        splitter.setSizes([160, 400])

        empty = QLabel("No collections yet. Each collection of this run will be listed here.")
        empty.setObjectName("muted")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.addWidget(empty)  # EMPTY_PAGE
        self.addWidget(splitter)  # LIST_PAGE

    def show_history(self, run: Run, collections: list[Collection]) -> None:
        self._run = run
        self._collections = collections
        self.table.blockSignals(True)  # rebuild quietly; the report is shown once at the end
        self.table.setRowCount(len(collections))
        for row, collection in enumerate(collections):
            counts = summary(collection)
            problems = counts["total"] - counts["copied"]
            values = [
                format_date(collection.started_at),
                STATUS_NAMES[collection.status],
                f"{counts['copied']} of {counts['total']}",
                str(problems) if problems else "–",
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
            self.table.item(row, 1).setForeground(status_color(collection.status))
        if collections:
            self.table.selectRow(0)
        self.table.blockSignals(False)
        self.setCurrentIndex(LIST_PAGE if collections else EMPTY_PAGE)
        if collections:
            self._on_row_selected(0)

    def _on_row_selected(self, row: int, *_ignored: int) -> None:
        if 0 <= row < len(self._collections):
            self.report.show_collection(self._collections[row], self._run)

    def _open_folder(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self._collections) and self._collections[row].folder:
            open_path(Path(self._collections[row].folder), self)
