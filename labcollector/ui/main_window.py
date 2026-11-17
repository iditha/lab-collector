"""The main window: the list of runs on the left, the selected run on the right."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from labcollector import __version__
from labcollector.config_models import AppConfig
from labcollector.records import Run
from labcollector.services.collection_service import CollectionService
from labcollector.services.run_service import RunService
from labcollector.services.settings_service import ConfigError, SettingsService
from labcollector.ui.collect_dialog import CollectDialog
from labcollector.ui.details_tab import DetailsTab
from labcollector.ui.files_tab import FilesTab
from labcollector.ui.helpers import format_date, open_path
from labcollector.ui.history_tab import HistoryTab
from labcollector.ui.run_form import RunDialog
from labcollector.ui.settings_dialog import SettingsDialog

EMPTY_PAGE, RUN_PAGE = 0, 1
DETAILS_TAB, FILES_TAB, HISTORY_TAB = 0, 1, 2


class MainWindow(QMainWindow):
    def __init__(
        self,
        run_service: RunService,
        collection_service: CollectionService,
        settings_service: SettingsService,
    ):
        super().__init__()
        self._run_service = run_service
        self._collection_service = collection_service
        self._settings_service = settings_service
        self._current: Run | None = None
        self.setWindowTitle(f"Lab Collector {__version__}")
        self.resize(1100, 700)

        splitter = QSplitter()
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_content())
        splitter.setStretchFactor(1, 1)  # extra width goes to the content, not the list
        splitter.setSizes([300, 800])
        self.setCentralWidget(splitter)
        self._build_menu()

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
        settings_button = QPushButton("Settings")
        settings_button.setToolTip("Where files are collected from and copied to, and UDP.")
        settings_button.clicked.connect(self.open_settings)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        layout = QVBoxLayout(sidebar)
        layout.addWidget(new_button)
        layout.addWidget(self.search)
        layout.addWidget(self.run_list)
        layout.addWidget(settings_button)
        return sidebar

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction("&New run…", QKeySequence.StandardKey.New, self._new_run)
        file_menu.addAction("&Settings…", QKeySequence("Ctrl+,"), self.open_settings)
        file_menu.addSeparator()
        file_menu.addAction("E&xit", QKeySequence.StandardKey.Quit, self.close)
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction("&About Lab Collector", self._show_about)

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
        collect_button = QPushButton("Collect now")
        collect_button.setObjectName("primary")
        collect_button.clicked.connect(self._collect)
        header.addWidget(collect_button, alignment=Qt.AlignmentFlag.AlignTop)

        self.details = DetailsTab()
        self.tabs = QTabWidget()
        self.files = FilesTab()
        self.history = HistoryTab()
        self.tabs.addTab(self.details, "Details")  # DETAILS_TAB
        self.tabs.addTab(self.files, "Files")  # FILES_TAB
        self.tabs.addTab(self.history, "History")  # HISTORY_TAB

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
        runs = self._run_service.search(self.search.text().strip())

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
        run = self._run_service.get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        if run is None:
            self._show_empty()
            return
        self._current = run
        self.run_title.setText(run.name)
        parts = [run.operator, run.location, f"created {format_date(run.created_at)}"]
        self.run_subtitle.setText("  ·  ".join(part for part in parts if part))
        self.details.show_run(run)
        self._show_collections(run)
        self.pages.setCurrentIndex(RUN_PAGE)

    def _show_collections(self, run: Run) -> None:
        collections = self._collection_service.history(run.id)
        self.files.show_collections(collections)
        self.history.show_history(run, collections)
        count = f" ({len(collections)})" if collections else ""
        self.tabs.setTabText(HISTORY_TAB, f"History{count}")

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
        dialog = RunDialog(self._run_service, parent=self)
        if dialog.exec():
            self.search.clear()  # make sure the new run is visible in the list
            self.refresh_runs(select_id=dialog.saved_run.id)

    def _edit_run(self) -> None:
        if self._current is None:
            return
        dialog = RunDialog(self._run_service, self._current, parent=self)
        if dialog.exec():
            self.refresh_runs(select_id=self._current.id)

    def _collect(self) -> None:
        if self._current is None:
            return
        config = self.load_config()  # re-read now, to pick up edits made outside the app
        if config is None:
            return
        dialog = CollectDialog(self._collection_service, self._current, config, parent=self)
        dialog.exec()
        if dialog.collection is not None:
            self._show_collections(self._current)
            self.tabs.setCurrentIndex(FILES_TAB)

    def open_settings(self) -> None:
        config = self.load_config()
        if config is not None:
            SettingsDialog(self._settings_service, config, parent=self).exec()

    def load_config(self) -> AppConfig | None:
        """Read config.yaml. If it's broken, explain why and offer to fix it.

        Returns the settings, or None if they're still broken (or the user closed the box).
        """
        try:
            return self._settings_service.load()
        except ConfigError as error:
            if self._offer_config_fix(str(error)):
                return self._settings_service.load()  # reset worked: carry on with defaults
            return None

    def _offer_config_fix(self, problem: str) -> bool:
        """Explain a broken config.yaml and offer to fix it. Returns True if it was reset."""
        box = QMessageBox(QMessageBox.Icon.Warning, "Settings problem", problem, parent=self)
        box.setInformativeText(
            "Fix config.yaml in a text editor, or reset it to the default settings "
            "(the current file is kept as config.yaml.bak)."
        )
        open_button = box.addButton("Open config.yaml", QMessageBox.ButtonRole.ActionRole)
        reset_button = box.addButton("Reset to default", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is open_button:
            open_path(self._settings_service.config_path, self)
            return False
        if box.clickedButton() is not reset_button:
            return False
        try:
            backup = self._settings_service.reset_to_default()
        except OSError as error:  # e.g. the data folder is read-only, or the file is locked
            QMessageBox.warning(
                self,
                "Couldn't reset",
                f"The settings couldn't be reset: {error.strerror or error}\n\n"
                f"Fix or delete this file by hand:\n{self._settings_service.config_path}",
            )
            return False
        QMessageBox.information(
            self, "Settings reset", f"Default settings restored.\nThe old file: {backup}"
        )
        return True

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Lab Collector",
            f"<b>Lab Collector {__version__}</b><p>Collects lab-run output files into an "
            "organized folder per run, keeps a history of every collection and reports "
            "missing, failed and corrupt files.</p>",
        )
