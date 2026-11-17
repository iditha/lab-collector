"""Dialog to add or edit one source folder and its rules.

It works like RunDialog: it edits a copy, OK checks it, and on success the result is in
``self.source``. Problems are shown in the dialog, which stays open so they can be fixed.
"""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from labcollector.services.settings_service import ConfigError, SettingsService

# Rules table: (setting name, column title), in column order.
RULE_COLUMNS = [
    ("name", "Rule name"),
    ("category", "Copy to folder"),
    ("prefix", "Name starts with"),
    ("extensions", "Extensions"),
    ("newest", "Newest N"),
    ("max_age_minutes", "Max age (min)"),
    ("expected", "Expected"),
]
EMPTY_MEANS_DEFAULT = {"newest", "max_age_minutes", "expected"}  # no limit / the default (1)
NEW_RULE = {"name": "All files", "category": "files", "prefix": "", "extensions": [], "expected": 1}

HINT = (
    "A rule picks files whose name starts with the prefix and ends with one of the extensions "
    "(e.g. .csv .log). Newest N keeps only the most recently modified files; Max age keeps files "
    "modified in the last N minutes. Leave them empty for no limit. Expected is how many files "
    "the rule should find: fewer are reported as missing."
)


class SourceDialog(QDialog):
    def __init__(self, settings: SettingsService, source: dict, parent: QWidget | None = None):
        """``source`` is the source as plain data; an empty name means a new source."""
        super().__init__(parent)
        self._settings = settings
        self._enabled = source.get("enabled", True)  # switched on/off in the sources list
        self.source: dict | None = None
        self.setWindowTitle("Edit source" if source.get("name") else "New source")
        self.resize(820, 460)

        self.name = QLineEdit(source.get("name", ""))
        self.name.setPlaceholderText("e.g. Instrument A")
        self.path = QLineEdit(source.get("path", ""))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        self.recursive = QCheckBox("Include subfolders")
        self.recursive.setChecked(source.get("recursive", False))

        self.rules = QTableWidget(0, len(RULE_COLUMNS))
        self.rules.setHorizontalHeaderLabels([title for _, title in RULE_COLUMNS])
        self.rules.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.rules.verticalHeader().hide()
        for rule in source.get("rules", []):
            self._add_rule_row(rule)
        add_rule = QPushButton("Add rule")
        add_rule.clicked.connect(lambda: self._add_rule_row(NEW_RULE))
        remove_rule = QPushButton("Remove rule")
        remove_rule.clicked.connect(lambda: self.rules.removeRow(self.rules.currentRow()))

        hint = QLabel(HINT)
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()

        Button = QDialogButtonBox.StandardButton
        self.buttons = QDialogButtonBox(Button.Ok | Button.Cancel)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)

        folder_row = QHBoxLayout()
        folder_row.addWidget(self.path)
        folder_row.addWidget(browse)
        form = QFormLayout()
        form.addRow("Name *", self.name)
        form.addRow("Folder *", folder_row)
        form.addRow("", self.recursive)
        rule_buttons = QHBoxLayout()
        rule_buttons.addWidget(add_rule)
        rule_buttons.addWidget(remove_rule)
        rule_buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Rules"))
        layout.addWidget(self.rules)
        layout.addLayout(rule_buttons)
        layout.addWidget(hint)
        layout.addWidget(self.error)
        layout.addWidget(self.buttons)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Source folder", self.path.text())
        if folder:
            self.path.setText(folder)

    def _add_rule_row(self, rule: dict) -> None:
        row = self.rules.rowCount()
        self.rules.insertRow(row)
        for column, (key, _) in enumerate(RULE_COLUMNS):
            value = rule.get(key)
            if key == "extensions":
                text = " ".join(value or [])
            elif value is None:
                text = ""
            elif isinstance(value, float) and value.is_integer():
                text = str(int(value))  # max age 120.0 is shown as 120
            else:
                text = str(value)
            self.rules.setItem(row, column, QTableWidgetItem(text))

    def _rule_from_row(self, row: int) -> dict:
        """One table row as rule settings. Text is passed on as typed; validation checks it."""
        rule = {}
        for column, (key, _) in enumerate(RULE_COLUMNS):
            item = self.rules.item(row, column)
            text = item.text().strip() if item else ""
            if key == "extensions":
                rule[key] = text.replace(",", " ").split()  # ".csv, .log" -> [".csv", ".log"]
            elif text or key not in EMPTY_MEANS_DEFAULT:
                rule[key] = text
        return rule

    def _accept(self) -> None:
        data = {
            "name": self.name.text().strip(),
            "path": self.path.text().strip(),
            "enabled": self._enabled,
            "recursive": self.recursive.isChecked(),
            "rules": [self._rule_from_row(row) for row in range(self.rules.rowCount())],
        }
        try:
            checked = self._settings.validate_source(data)
        except ConfigError as error:
            self.error.setText(str(error))
            self.error.show()
            return
        self.source = checked.model_dump(mode="json")  # cleaned, e.g. "CSV" -> ".csv"
        self.accept()
