"""The Settings dialog: where collected files go, which folders to collect from, and UDP.

Sources are edited one at a time in SourceDialog. Save checks all settings together and
writes config.yaml through SettingsService; problems are listed in the dialog by name.
"""

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from labcollector.config_models import AppConfig, UdpSettings
from labcollector.services.settings_service import ConfigError, SettingsService
from labcollector.ui.helpers import ERROR_COLOR, SUCCESS_COLOR, open_path
from labcollector.ui.source_dialog import NEW_RULE, SourceDialog


class SettingsDialog(QDialog):
    def __init__(self, settings: SettingsService, config: AppConfig, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings = settings
        self._sources: list[dict] = []  # the sources being edited, as plain data
        self._file_changed_at: float | None = None  # when config.yaml was last changed, at load
        self.setWindowTitle("Settings")
        self.resize(720, 620)

        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_output_group())
        layout.addWidget(self._build_sources_group(), stretch=1)
        layout.addWidget(self._build_udp_group())
        layout.addWidget(self.error)
        layout.addLayout(self._build_buttons())

        self._fill(config)

    # --- Building the dialog ------------------------------------------------------------

    def _build_output_group(self) -> QGroupBox:
        self.output_root = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_output)

        group = QGroupBox("Output: where collected files are copied")
        row = QHBoxLayout(group)
        row.addWidget(self.output_root)
        row.addWidget(browse)
        return group

    def _build_sources_group(self) -> QGroupBox:
        self.source_list = QListWidget()
        self.source_list.setToolTip("Untick a source to skip it when collecting.")
        self.source_list.itemChanged.connect(self._on_tick_changed)
        self.source_list.itemDoubleClicked.connect(lambda: self._edit_source())

        self.add_button = QPushButton("Add…")
        self.add_button.clicked.connect(self._add_source)
        self.edit_button = QPushButton("Edit source and rules…")
        self.edit_button.clicked.connect(self._edit_source)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._remove_source)
        buttons = QVBoxLayout()
        for button in (self.add_button, self.edit_button, self.remove_button):
            buttons.addWidget(button)
        buttons.addStretch()

        group = QGroupBox("Sources and their rules (untick a source to skip it)")
        row = QHBoxLayout(group)
        row.addWidget(self.source_list)
        row.addLayout(buttons)
        return group

    def _build_udp_group(self) -> QGroupBox:
        self.udp_enabled = QCheckBox("Send a UDP message after each collection")
        self.udp_host = QLineEdit()
        self.udp_host.setPlaceholderText("IP address or computer name, e.g. 192.168.1.50")
        self.udp_port = QSpinBox()
        self.udp_port.setRange(1, 65535)
        test = QPushButton("Send test message")
        test.clicked.connect(self._send_test_message)
        self.udp_result = QLabel()
        self.udp_result.setWordWrap(True)

        target = QHBoxLayout()
        target.addWidget(self.udp_host, stretch=1)
        target.addWidget(QLabel("Port"))
        target.addWidget(self.udp_port)
        target.addWidget(test)

        group = QGroupBox("Remote computer (UDP)")
        form = QFormLayout(group)
        form.addRow(self.udp_enabled)
        form.addRow("Send to", target)
        form.addRow(self.udp_result)
        return group

    def _build_buttons(self) -> QHBoxLayout:
        open_file = QPushButton("Open config.yaml")
        open_file.setToolTip(str(self._settings.config_path))
        open_file.clicked.connect(lambda: open_path(self._settings.config_path, self))
        self.reload_button = QPushButton("Reload from file")
        self.reload_button.setToolTip("Discard the changes made here and read config.yaml again.")
        self.reload_button.clicked.connect(self._reload)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self._save)

        row = QHBoxLayout()
        row.addWidget(open_file)
        row.addWidget(self.reload_button)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(self.save_button)
        return row

    # --- Showing the settings -----------------------------------------------------------

    def _fill(self, config: AppConfig) -> None:
        self.output_root.setText(config.output_root)
        self.udp_enabled.setChecked(config.udp.enabled)
        self.udp_host.setText(config.udp.host)
        self.udp_port.setValue(config.udp.port)
        self._sources = config.model_dump(mode="json")["sources"]
        self._show_sources(select=0)
        self._file_changed_at = self._settings.file_changed_at()

    def _show_sources(self, select: int) -> None:
        self.source_list.blockSignals(True)  # adding ticks would otherwise fire itemChanged
        self.source_list.clear()
        for source in self._sources:
            # The rule count hints that each source has its own rules, edited with the source.
            count = len(source["rules"])
            rules = f"{count} rule" if count == 1 else f"{count} rules"
            item = QListWidgetItem(f"{source['name']}  ·  {rules}\n{source['path']}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = Qt.CheckState.Checked if source["enabled"] else Qt.CheckState.Unchecked
            item.setCheckState(checked)
            self.source_list.addItem(item)
        self.source_list.blockSignals(False)
        if self._sources:
            self.source_list.setCurrentRow(min(select, len(self._sources) - 1))

    # --- Actions ------------------------------------------------------------------------

    def _on_tick_changed(self, item: QListWidgetItem) -> None:
        row = self.source_list.row(item)
        self._sources[row]["enabled"] = item.checkState() == Qt.CheckState.Checked

    def _add_source(self) -> None:
        new = {"name": "", "path": "", "rules": [dict(NEW_RULE)]}
        dialog = SourceDialog(self._settings, new, parent=self)
        if dialog.exec():
            self._sources.append(dialog.source)
            self._show_sources(select=len(self._sources) - 1)

    def _edit_source(self) -> None:
        row = self.source_list.currentRow()
        if row < 0:
            return
        # The dialog edits a copy, so Cancel leaves the original untouched.
        dialog = SourceDialog(self._settings, copy.deepcopy(self._sources[row]), parent=self)
        if dialog.exec():
            self._sources[row] = dialog.source
            self._show_sources(select=row)

    def _remove_source(self) -> None:
        row = self.source_list.currentRow()
        if row >= 0:
            del self._sources[row]
            self._show_sources(select=row)

    def _browse_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Output folder", self.output_root.text())
        if folder:
            self.output_root.setText(folder)

    def _send_test_message(self) -> None:
        host = self.udp_host.text().strip()
        if not host:
            self._show_udp_result("Enter the remote computer's address first.", ok=False)
            return
        error = self._settings.send_test_message(UdpSettings(host=host, port=self.udp_port.value()))
        if error:
            self._show_udp_result(f"Not sent: {error}", ok=False)
        else:
            self._show_udp_result(
                f"Test message sent to {host}:{self.udp_port.value()}. UDP has no reply, "
                "so check that the other computer received it.",
                ok=True,
            )

    def _show_udp_result(self, text: str, ok: bool) -> None:
        color = SUCCESS_COLOR if ok else ERROR_COLOR
        self.udp_result.setStyleSheet(f"color: {color.name()}")
        self.udp_result.setText(text)

    def _reload(self) -> None:
        try:
            config = self._settings.load()
        except ConfigError as error:
            self._show_error(str(error))
            return
        self.error.hide()
        self._fill(config)

    def _save(self) -> None:
        data = {
            "output_root": self.output_root.text().strip(),
            "udp": {
                "enabled": self.udp_enabled.isChecked(),
                "host": self.udp_host.text().strip(),
                "port": self.udp_port.value(),
            },
            "sources": self._sources,
        }
        try:
            config = self._settings.validate(data)
        except ConfigError as error:
            self._show_error(str(error))  # keep the dialog open so the user can fix it
            return
        if not self._ok_to_overwrite():
            return
        try:
            self._settings.save(config)
        except OSError as error:
            self._show_error(f"Couldn't save {self._settings.config_path}: {error}")
            return
        self.accept()

    def _ok_to_overwrite(self) -> bool:
        """If config.yaml changed since it was loaded (e.g. edited in Notepad), ask first."""
        if self._settings.file_changed_at() == self._file_changed_at:
            return True
        answer = QMessageBox.question(
            self,
            "config.yaml was changed",
            "config.yaml was changed outside the app after Settings opened. Saving will "
            "replace those changes.\n\nSave anyway? (Choose No, then “Reload from file”, to "
            "see the other changes.)",
            defaultButton=QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.show()
