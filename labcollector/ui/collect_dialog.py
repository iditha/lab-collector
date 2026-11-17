"""The Collect dialog: preview what will be collected, collect with progress, show the report.

PREVIEW  -> "Start collection" ->  RUNNING  -> (finished) ->  RESULT
"""

from PySide6.QtCore import QThread, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from labcollector.config_models import AppConfig
from labcollector.records import Collection, Run
from labcollector.services.collection_service import CollectionService, RulePlan, preview
from labcollector.ui.helpers import WARNING_COLOR
from labcollector.ui.report_view import ReportView
from labcollector.ui.worker import CollectionWorker

PREVIEW, RUNNING, RESULT = 0, 1, 2


class CollectDialog(QDialog):
    """After it closes, ``collection`` holds the result (None if the user didn't collect)."""

    def __init__(
        self,
        service: CollectionService,
        run: Run,
        config: AppConfig,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._service = service
        self._run = run
        self._config = config
        self._thread: QThread | None = None
        self._worker: CollectionWorker | None = None
        self.collection: Collection | None = None
        self.setWindowTitle(f"Collect files: {run.name}")
        self.resize(760, 560)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_preview_page())  # PREVIEW
        self.pages.addWidget(self._build_running_page())  # RUNNING
        self.pages.addWidget(self._build_result_page())  # RESULT
        QVBoxLayout(self).addWidget(self.pages)

        self._show_preview()

    # --- Pages ---------------------------------------------------------------------

    def _build_preview_page(self) -> QWidget:
        self.preview_tree = QTreeWidget()
        self.preview_tree.setHeaderLabels(["Source / rule", "Copied to", "Found"])
        self.preview_tree.setColumnWidth(0, 360)
        self.preview_summary = QLabel()
        self.preview_summary.setWordWrap(True)

        self.start_button = QPushButton("Start collection")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self._start)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(f"Files will be copied to: {self._config.output_root}"))
        layout.addWidget(self.preview_tree)
        layout.addWidget(self.preview_summary)
        layout.addLayout(_button_row(cancel, self.start_button))
        return page

    def _build_running_page(self) -> QWidget:
        self.progress_text = QLabel("Starting…")
        self.progress_bar = QProgressBar()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        layout.addWidget(self.progress_text)
        layout.addWidget(self.progress_bar)
        layout.addStretch()
        layout.addLayout(_button_row(self.cancel_button))
        return page

    def _build_result_page(self) -> QWidget:
        self.report_view = ReportView()
        close = QPushButton("Close")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.report_view)
        layout.addLayout(_button_row(close))
        return page

    # --- Steps ---------------------------------------------------------------------

    def _show_preview(self) -> None:
        if not self._config.enabled_sources:
            self.preview_summary.setText(
                "No source folders are enabled, so there is nothing to collect. "
                "Add or enable sources in Settings."
            )
            self.start_button.setEnabled(False)
            return

        plans = preview(self._config)
        for plan in plans:
            self.preview_tree.addTopLevelItem(_plan_item(plan))
        total = sum(len(plan.files) for plan in plans)
        short = sum(1 for plan in plans if plan.error or len(plan.files) < plan.expected)
        text = f"{total} files will be copied and verified."
        if short:
            rules = "1 rule" if short == 1 else f"{short} rules"
            text += f" {rules} found fewer files than expected (marked ⚠)."
        self.preview_summary.setText(text)

    def _start(self) -> None:
        self.pages.setCurrentIndex(RUNNING)
        self._thread = QThread(self)
        self._worker = CollectionWorker(self._service, self._run, self._config)
        self._worker.moveToThread(self._thread)  # its run() will execute in the new thread
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._worker.deleteLater)  # free the worker afterwards
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    # The @Slot methods below receive the worker's signals. Qt runs them on the dialog's
    # own thread, the only thread allowed to change widgets.

    @Slot(int, int, str)
    def _on_progress(self, done: int, total: int, message: str) -> None:
        self.progress_bar.setMaximum(max(total, 1))
        self.progress_bar.setValue(done)
        self.progress_text.setText(f"{message}  ({done} of {total})")

    @Slot(object)
    def _on_finished(self, collection: Collection) -> None:
        self._stop_thread()
        self.collection = collection
        self.report_view.show_collection(collection, self._run)
        self.pages.setCurrentIndex(RESULT)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._stop_thread()
        self.report_view.setPlainText(f"The collection couldn't be completed:\n\n{message}")
        self.pages.setCurrentIndex(RESULT)

    def _stop_thread(self) -> None:
        self._thread.quit()
        self._thread.wait()  # make sure the thread has ended before it can be deleted

    def reject(self) -> None:
        """Esc, the window's X and Cancel all come here. While copying, ask to stop instead."""
        if self.pages.currentIndex() == RUNNING:
            self._worker.cancel()
            self.cancel_button.setEnabled(False)
            self.progress_text.setText("Cancelling after the current file…")
            return  # when the worker stops, the report of what was copied is shown
        super().reject()


def _plan_item(plan: RulePlan) -> QTreeWidgetItem:
    found = (
        f"{len(plan.files)} of {plan.expected} expected" if plan.expected else str(len(plan.files))
    )
    item = QTreeWidgetItem([f"{plan.source} / {plan.rule}", f"{plan.category}/", found])
    if plan.error or len(plan.files) < plan.expected:
        item.setText(0, "⚠ " + item.text(0))
        item.setToolTip(
            0, plan.error or "Fewer files than expected: the rest will be reported missing."
        )
        for column in range(3):
            item.setForeground(column, WARNING_COLOR)
    for info in plan.files:
        item.addChild(QTreeWidgetItem([info.path.name]))
    return item


def _button_row(*buttons: QPushButton) -> QHBoxLayout:
    row = QHBoxLayout()
    row.addStretch()
    for button in buttons:
        row.addWidget(button)
    return row
