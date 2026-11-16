"""The Details tab: a read-only view of a run's information."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

from labcollector.records import Run

FIELDS = [
    ("Operator", "operator"),
    ("Location", "location"),
    ("Software / baseline", "sw_baseline"),
    ("Description", "description"),
    ("Results", "results"),
]


class DetailsTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._values: dict[str, QLabel] = {}
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        form.setVerticalSpacing(14)
        for label, field in FIELDS:
            value = QLabel()
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._values[field] = value
            caption = QLabel(label)
            caption.setObjectName("fieldLabel")
            form.addRow(caption, value)

    def show_run(self, run: Run) -> None:
        for field, label in self._values.items():
            text = getattr(run, field)
            label.setText(text or "Not filled in")
            label.setProperty("empty", not text)  # styled grey in style.qss
            label.style().polish(label)  # re-apply the style after the property changed
