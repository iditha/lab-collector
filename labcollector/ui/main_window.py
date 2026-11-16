"""The main window: the list of runs on the left, the selected run on the right."""

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from labcollector.records import Run
from labcollector.services.run_service import RunService
from labcollector.ui.details_tab import DetailsTab
from labcollector.ui.run_form import RunDialog

EMPTY_PAGE, RUN_PAGE = 0, 1


class MainWindow(QMainWindow):
    def __init__(self, runs: RunService):
        super().__init__()
        self._runs = runs
        self._current: Run | None = None
        self.setWindowTitle("Lab Collector")
        self.resize(1100, 700)

        splitter = QSplitter()
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_content())
        splitter.setStretchFactor(1, 1)  # extra width goes to the content, not the list
        splitter.setSizes([300, 800])
        self.setCentralWidget(splitter)

        self.refresh_runs()

    # --- Building the window --------------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search runs (name, operator, location)")
        self.search.setClearButtonEnabled(True)
        # The lambda is needed: textChanged sends the typed text, which refresh_runs would
        # otherwise receive as its select_id argument.
        self.search.textChanged.connect(lambda: self.refresh_runs())

        self.run_list = QListWidget()
        self.run_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.run_list.setTextElideMode(Qt.TextElideMode.ElideRight)  # long names end with "…"
        self.run_list.currentItemChanged.connect(self._on_run_selected)

        new_button = QPushButton("+  New run")
        new_button.setObjectName("primary")
        new_button.clicked.connect(self._new_run)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        layout = QVBoxLayout(sidebar)
        layout.addWidget(new_button)
        layout.addWidget(self.search)
        layout.addWidget(self.run_list)
        return sidebar

    def _build_content(self) -> QWidget:
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_empty_page())  # EMPTY_PAGE
        self.pages.addWidget(self._build_run_page())  # RUN_PAGE
        return self.pages

    def _build_empty_page(self) -> QWidget:
        self.empty_title = QLabel()
        self.empty_title.setObjectName("emptyTitle")
        self.empty_text = QLabel()
        self.empty_text.setObjectName("muted")
        self.empty_button = QPushButton("Create your first run")
        self.empty_button.setObjectName("primary")
        self.empty_button.clicked.connect(self._new_run)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        for widget in (self.empty_title, self.empty_text, self.empty_button):
            layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        return page

    def _build_run_page(self) -> QWidget:
        self.run_title = QLabel()
        self.run_title.setObjectName("runTitle")
        self.run_subtitle = QLabel()
        self.run_subtitle.setObjectName("muted")

        edit_button = QPushButton("Edit details")
        edit_button.clicked.connect(self._edit_run)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(self.run_title)
        titles.addWidget(self.run_subtitle)
        header.addLayout(titles)
        header.addStretch()
        header.addWidget(edit_button, alignment=Qt.AlignmentFlag.AlignTop)

        self.details = DetailsTab()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.details, "Details")
        self.tabs.addTab(_placeholder("Collected files will appear here."), "Files")
        self.tabs.addTab(_placeholder("Past collections will appear here."), "History")

        page = QWidget()
        page.setObjectName("runPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addLayout(header)
        layout.addSpacing(8)
        layout.addWidget(self.tabs)
        return page

    # --- Behaviour ----------------------------------------------------------------------

    def refresh_runs(self, select_id: int | None = None) -> None:
        """Reload the list (keeping the search filter) and select a run if possible."""
        if select_id is None and self._current:
            select_id = self._current.id
        runs = self._runs.search(self.search.text().strip())

        self.run_list.blockSignals(True)  # don't react to selection changes while rebuilding
        self.run_list.clear()
        for run in runs:
            item = QListWidgetItem(f"{run.name}\n{run.operator}  ·  {format_date(run.created_at)}")
            item.setData(Qt.ItemDataRole.UserRole, run.id)
            self.run_list.addItem(item)
        self.run_list.blockSignals(False)

        if not runs:
            self._show_empty()
            return
        row = next((i for i, run in enumerate(runs) if run.id == select_id), 0)
        self.run_list.setCurrentRow(row)  # fires currentItemChanged -> _on_run_selected

    def _on_run_selected(
        self, item: QListWidgetItem | None, _previous: QListWidgetItem | None = None
    ) -> None:
        run = self._runs.get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        if run is None:
            self._show_empty()
            return
        self._current = run
        self.run_title.setText(run.name)
        parts = [run.operator, run.location, f"created {format_date(run.created_at)}"]
        self.run_subtitle.setText("  ·  ".join(part for part in parts if part))
        self.details.show_run(run)
        self.pages.setCurrentIndex(RUN_PAGE)

    def _show_empty(self) -> None:
        self._current = None
        searching = bool(self.search.text().strip())
        self.empty_title.setText("No matching runs" if searching else "No runs yet")
        self.empty_text.setText(
            "Try a different search." if searching else "Create a run, then collect its files."
        )
        self.empty_button.setVisible(not searching)
        self.pages.setCurrentIndex(EMPTY_PAGE)

    def _new_run(self) -> None:
        dialog = RunDialog(self._runs, parent=self)
        if dialog.exec():
            self.search.clear()  # make sure the new run is visible in the list
            self.refresh_runs(select_id=dialog.saved_run.id)

    def _edit_run(self) -> None:
        if self._current is None:
            return
        dialog = RunDialog(self._runs, self._current, parent=self)
        if dialog.exec():
            self.refresh_runs(select_id=self._current.id)


def format_date(iso_text: str) -> str:
    """'2026-11-16T11:13:09' -> '16 Nov 2026, 11:13'."""
    try:
        return datetime.fromisoformat(iso_text).strftime("%d %b %Y, %H:%M")
    except ValueError:
        return iso_text


def _placeholder(text: str) -> QWidget:
    label = QLabel(text)
    label.setObjectName("muted")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label
