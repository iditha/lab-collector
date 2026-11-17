"""Dialog to create a new run or edit an existing one."""

import os
from dataclasses import replace

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from labcollector.records import Run
from labcollector.services.run_service import RunService, RunValidationError


class RunDialog(QDialog):
    """Create a run (``run=None``) or edit one. After Save, ``saved_run`` holds the result."""

    def __init__(
        self, run_service: RunService, run: Run | None = None, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self._run_service = run_service
        self._editing = run
        self.saved_run: Run | None = None
        self.setWindowTitle("Edit run" if run else "New run")
        self.setMinimumWidth(520)

        self.name = QLineEdit()
        self.operator = QLineEdit()
        self.location = QLineEdit()
        self.location.setPlaceholderText("Lab or site where the run took place")
        self.sw_baseline = _text_box("Software versions or baseline used")
        self.description = _text_box("What was done and what happened during the run")
        self.results = _text_box("Results obtained (can be filled in later)")

        form = QFormLayout()
        form.addRow("Name *", self.name)
        form.addRow("Operator *", self.operator)
        form.addRow("Location", self.location)
        form.addRow("Software / baseline", self.sw_baseline)
        form.addRow("Description", self.description)
        form.addRow("Results", self.results)

        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()

        Button = QDialogButtonBox.StandardButton
        self.buttons = QDialogButtonBox(Button.Save | Button.Cancel)
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addWidget(self.buttons)

        if run:
            self._fill(run)
        else:
            self.name.setPlaceholderText("Unique name, e.g. RUN-2026-031")
            # A good guess: usually the person logged in to Windows ran it. They can change it.
            self.operator.setText(os.environ.get("USERNAME", ""))

    def _fill(self, run: Run) -> None:
        self.name.setText(run.name)
        self.name.setEnabled(False)
        self.name.setToolTip("A run's name can't be changed: it names the run's folders.")
        self.operator.setText(run.operator)
        self.location.setText(run.location)
        self.sw_baseline.setPlainText(run.sw_baseline)
        self.description.setPlainText(run.description)
        self.results.setPlainText(run.results)
        self.operator.setFocus()

    def _save(self) -> None:
        fields = {
            "name": self.name.text(),
            "operator": self.operator.text(),
            "location": self.location.text(),
            "sw_baseline": self.sw_baseline.toPlainText(),
            "description": self.description.toPlainText(),
            "results": self.results.toPlainText(),
        }  # passed as typed: the service trims and validates
        try:
            if self._editing:
                run = replace(self._editing, **fields)  # a copy that keeps id and created_at
                self._run_service.update(run)
            else:
                run = self._run_service.create(Run(**fields))
        except RunValidationError as error:
            self.error.setText(str(error))  # keep the dialog open so the user can fix it
            self.error.show()
            return
        self.saved_run = run
        self.accept()


def _text_box(placeholder: str) -> QPlainTextEdit:
    box = QPlainTextEdit()
    box.setPlaceholderText(placeholder)
    box.setTabChangesFocus(True)  # Tab moves to the next field instead of typing a tab
    box.setFixedHeight(72)
    return box
