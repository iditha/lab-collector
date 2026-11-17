"""UI tests. Qt runs "offscreen" (set in conftest.py), so no window opens."""

import os
import sys
import time

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
)

from labcollector import __version__
from labcollector.config_models import AppConfig, Rule, Source, UdpSettings
from labcollector.records import CollectionStatus, Run
from labcollector.services.collection_service import CollectionService
from labcollector.services.run_service import RunService
from labcollector.services.settings_service import SettingsService
from labcollector.ui import files_tab, history_tab, settings_dialog
from labcollector.ui.collect_dialog import PREVIEW, RESULT, RUNNING, CollectDialog
from labcollector.ui.helpers import install_error_handler
from labcollector.ui.main_window import EMPTY_PAGE, RUN_PAGE, MainWindow
from labcollector.ui.run_form import RunDialog
from labcollector.ui.settings_dialog import SettingsDialog
from labcollector.ui.source_dialog import NEW_RULE, SourceDialog

SAVE = QDialogButtonBox.StandardButton.Save


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def runs(repository):
    return RunService(repository)


@pytest.fixture
def config(tmp_path):
    """A source folder with two measurement files, and a rule that expects three."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "MEAS_1.csv").write_text("1")
    (source / "MEAS_2.csv").write_text("2")
    rule = Rule(name="Measurements", category="measurements", prefix="MEAS_", expected=3)
    return AppConfig(
        output_root=str(tmp_path / "out"),
        udp=UdpSettings(enabled=False),
        sources=[Source(name="Instrument", path=str(source), rules=[rule])],
    )


@pytest.fixture
def settings(tmp_path, config):
    """A SettingsService whose config.yaml (in a temporary folder) holds ``config``."""
    service = SettingsService(tmp_path / "config.yaml", tmp_path / "out")
    service.save(config)
    return service


@pytest.fixture
def make_window(runs, repository, settings):
    return lambda: MainWindow(runs, CollectionService(repository), settings)


def answer_dialogs(*button_texts: str) -> None:
    """Click buttons in the message boxes that will open next, in order.

    A message box waits for the user, so the clicks are scheduled before it opens: Qt runs
    the timer while the box is waiting, and the click closes it like a real user would.
    """
    remaining = list(button_texts)

    def click_next() -> None:
        box = QApplication.activeModalWidget()
        if box is None:  # not open yet: try again shortly
            QTimer.singleShot(10, click_next)
            return
        text = remaining.pop(0)
        button = next(b for b in box.findChildren(QAbstractButton) if b.text() == text)
        button.click()
        if remaining:
            QTimer.singleShot(10, click_next)

    QTimer.singleShot(10, click_next)


def collect_and_wait(dialog: CollectDialog, timeout: float = 10.0) -> None:
    """Click Start and wait for the background thread to finish.

    QTest.qWait keeps processing Qt events while waiting, which is what delivers the
    worker's "finished" signal to the dialog.
    """
    dialog.start_button.click()
    wait_for_result(dialog, timeout)


def wait_for_result(dialog: CollectDialog, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while dialog.pages.currentIndex() != RESULT:
        assert time.monotonic() < deadline, "the collection didn't finish in time"
        QTest.qWait(20)


def test_empty_state_when_there_are_no_runs(app, runs, make_window):
    window = make_window()
    assert window.pages.currentIndex() == EMPTY_PAGE
    assert window.empty_title.text() == "No runs yet"


def test_newest_run_is_selected_and_shown(app, runs, make_window):
    runs.create(Run(name="RUN-1", operator="Avi"))
    runs.create(Run(name="RUN-2", operator="Dana", location="Lab 2"))
    window = make_window()
    assert window.pages.currentIndex() == RUN_PAGE
    assert window.run_title.text() == "RUN-2"
    assert "Dana" in window.run_subtitle.text()


def test_clicking_another_run_shows_it(app, runs, make_window):
    runs.create(Run(name="RUN-1", operator="Avi"))
    runs.create(Run(name="RUN-2", operator="Dana"))
    window = make_window()
    window.run_list.setCurrentRow(1)  # the list is newest first, so row 1 is RUN-1
    assert window.run_title.text() == "RUN-1"


def test_search_filters_the_list(app, runs, make_window):
    runs.create(Run(name="Alpha", operator="Dana"))
    runs.create(Run(name="Beta", operator="Avi"))
    window = make_window()
    window.search.setText("avi")
    assert window.run_list.count() == 1
    window.search.setText("zzz")
    assert window.pages.currentIndex() == EMPTY_PAGE
    assert window.empty_title.text() == "No matching runs"


def test_dialog_creates_a_run(app, runs):
    dialog = RunDialog(runs)
    dialog.name.setText("RUN-9")
    dialog.operator.setText("Dana")
    dialog.results.setPlainText("Peak at 412 nm\n")
    dialog.buttons.button(SAVE).click()
    assert dialog.saved_run.id is not None
    assert runs.find("RUN-9").results == "Peak at 412 nm"


def test_new_run_operator_defaults_to_windows_user(app, runs, monkeypatch):
    monkeypatch.setenv("USERNAME", "dana")
    assert RunDialog(runs).operator.text() == "dana"
    assert RunDialog(runs, runs.create(Run(name="R", operator="Avi"))).operator.text() == "Avi"


def test_dialog_shows_every_error_and_stays_open(app, runs):
    dialog = RunDialog(runs)
    dialog.name.setText("bad/name")
    dialog.operator.clear()
    dialog.buttons.button(SAVE).click()
    assert dialog.saved_run is None
    assert "must not contain /" in dialog.error.text()
    assert "Operator is required" in dialog.error.text()


def test_dialog_reports_duplicate_name(app, runs):
    runs.create(Run(name="RUN-1", operator="Dana"))
    dialog = RunDialog(runs)
    dialog.name.setText("run-1")
    dialog.operator.setText("Avi")
    dialog.buttons.button(SAVE).click()
    assert "already exists" in dialog.error.text()


def test_edit_keeps_name_and_saves_changes(app, runs):
    run = runs.create(Run(name="RUN-1", operator="Dana"))
    dialog = RunDialog(runs, run)
    assert not dialog.name.isEnabled()
    dialog.results.setPlainText("Within spec")
    dialog.buttons.button(SAVE).click()
    saved = runs.get(run.id)
    assert (saved.name, saved.results, saved.created_at) == ("RUN-1", "Within spec", run.created_at)


# --- Collecting (M4) ---------------------------------------------------------------


def test_collect_dialog_previews_and_warns_about_missing_files(app, repository, run, config):
    dialog = CollectDialog(CollectionService(repository), run, config)
    assert dialog.pages.currentIndex() == PREVIEW
    rule_row = dialog.preview_tree.topLevelItem(0)
    assert rule_row.text(0) == "⚠ Instrument / Measurements"
    assert rule_row.text(2) == "2 of 3 expected"
    assert rule_row.childCount() == 2
    assert "2 files will be copied" in dialog.preview_summary.text()


def test_collect_dialog_runs_in_background_and_shows_report(app, repository, run, config):
    dialog = CollectDialog(CollectionService(repository), run, config)
    collect_and_wait(dialog)
    assert dialog.collection.status == CollectionStatus.PARTIAL
    assert "Collection partly succeeded" in dialog.report_view.toPlainText()


def test_no_sources_means_nothing_to_start(app, repository, run, tmp_path):
    dialog = CollectDialog(CollectionService(repository), run, AppConfig(output_root=str(tmp_path)))
    assert not dialog.start_button.isEnabled()
    assert "No source folders" in dialog.preview_summary.text()


def test_cancel_while_running_stops_and_still_shows_a_report(app, repository, run, config):
    dialog = CollectDialog(CollectionService(repository), run, config)
    dialog.start_button.click()
    assert dialog.pages.currentIndex() == RUNNING
    dialog.cancel_button.click()  # same as pressing Esc or closing the window
    assert "Cancelling" in dialog.progress_text.text()
    assert not dialog.cancel_button.isEnabled()
    wait_for_result(dialog)
    assert dialog.collection is not None  # the (partial) collection is still recorded


def test_files_and_history_tabs_show_collections(app, runs, repository, config, make_window):
    run = runs.create(Run(name="RUN-1", operator="Dana"))
    CollectionService(repository).collect(run, config)
    CollectionService(repository).collect(run, config)
    window = make_window()

    assert window.tabs.tabText(2) == "History (2)"
    newest = window.files.tree.topLevelItem(0)
    assert window.files.tree.topLevelItemCount() == 2
    assert newest.isExpanded()
    assert newest.child(0).text(0) == "measurements  (2)"
    assert newest.child(0).child(0).text(2) == "Verified"

    assert window.history.table.rowCount() == 2
    assert window.history.table.item(0, 1).text() == "Partial"
    assert window.history.table.item(0, 2).text() == "2 of 3"
    assert "Collection partly succeeded" in window.history.report.toPlainText()


def test_new_run_has_empty_files_and_history(app, runs, make_window):
    runs.create(Run(name="RUN-1", operator="Dana"))
    window = make_window()
    assert window.files.currentIndex() == files_tab.EMPTY_PAGE
    assert window.history.currentIndex() == history_tab.EMPTY_PAGE
    assert window.tabs.tabText(2) == "History"


# --- Settings (M5) -----------------------------------------------------------------


def test_window_title_shows_the_version(app, make_window):
    assert make_window().windowTitle() == f"Lab Collector {__version__}"


def test_settings_dialog_shows_the_current_settings(app, settings, config):
    dialog = SettingsDialog(settings, config)
    assert dialog.output_root.text() == config.output_root
    assert dialog.source_list.count() == 1
    assert dialog.source_list.item(0).text().startswith("Instrument  ·  1 rule\n")
    assert dialog.source_list.item(0).checkState() == Qt.CheckState.Checked
    assert not dialog.udp_enabled.isChecked()


def test_unticking_a_source_and_saving_writes_it_to_the_file(app, settings, config):
    dialog = SettingsDialog(settings, config)
    dialog.source_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    dialog.output_root.setText("D:/LabRuns")
    dialog.save_button.click()
    saved = settings.load()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert saved.output_root == "D:/LabRuns"
    assert saved.sources[0].enabled is False


def test_invalid_settings_are_shown_and_not_saved(app, settings, config):
    before = settings.config_path.read_text(encoding="utf-8")
    dialog = SettingsDialog(settings, config)
    dialog.output_root.setText("")
    dialog.save_button.click()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "output_root" in dialog.error.text()
    assert settings.config_path.read_text(encoding="utf-8") == before


def test_editing_a_source_replaces_it(app, settings, config, monkeypatch):
    class FakeSourceDialog:  # stands in for the real dialog, which would wait for a user
        def __init__(self, _settings, source, parent=None):
            self.source = {**source, "name": "Renamed"}

        def exec(self):
            return True

    monkeypatch.setattr(settings_dialog, "SourceDialog", FakeSourceDialog)
    dialog = SettingsDialog(settings, config)
    dialog.source_list.setCurrentRow(0)
    dialog.edit_button.click()
    assert dialog.source_list.item(0).text().startswith("Renamed")


def test_source_dialog_cleans_valid_input(app, settings):
    dialog = SourceDialog(settings, {"name": "", "path": "", "rules": [NEW_RULE]})
    dialog.name.setText("Scope")
    dialog.path.setText("C:/Scope/Out")
    dialog.rules.item(0, 3).setText("CSV, log")  # the Extensions column
    dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    assert dialog.source["name"] == "Scope"
    assert dialog.source["rules"][0]["extensions"] == [".csv", ".log"]


def test_source_dialog_shows_errors_and_stays_open(app, settings):
    dialog = SourceDialog(settings, {"name": "", "path": "", "rules": [NEW_RULE]})
    dialog.rules.item(0, 4).setText("lots")  # Newest N must be a number
    dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    assert dialog.source is None
    assert "name" in dialog.error.text() and "newest" in dialog.error.text()


def test_broken_config_can_be_reset_with_the_real_button(app, settings, make_window):
    window = make_window()
    settings.config_path.write_text("udp: host: oops\n", encoding="utf-8")

    answer_dialogs("Reset to default", "OK")  # the problem box, then "Settings reset"
    config = window.load_config()

    assert config is not None and config.sources == []  # carries on with default settings
    backup = settings.config_path.with_name("config.yaml.bak")
    assert backup.read_text(encoding="utf-8") == "udp: host: oops\n"  # the old file is kept


def test_save_warns_before_overwriting_outside_edits(app, settings, config, monkeypatch):
    dialog = SettingsDialog(settings, config)
    stamp = settings.config_path.stat().st_mtime
    os.utime(settings.config_path, (stamp + 10, stamp + 10))  # "edited in Notepad"
    dialog.output_root.setText("D:/LabRuns")

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    dialog.save_button.click()
    assert settings.load().output_root != "D:/LabRuns"  # No: the outside edit is kept

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog.save_button.click()
    assert settings.load().output_root == "D:/LabRuns"  # Yes: saved anyway


def test_reload_reads_the_file_again(app, settings, config):
    dialog = SettingsDialog(settings, config)
    settings.save(config.model_copy(update={"output_root": "E:/Elsewhere"}))
    dialog.reload_button.click()
    assert dialog.output_root.text() == "E:/Elsewhere"


def test_adding_a_source(app, settings, config, monkeypatch):
    class FakeSourceDialog:  # stands in for the real dialog, which would wait for a user
        def __init__(self, _settings, source, parent=None):
            self.source = {**source, "name": "Scope", "path": "C:/Scope", "enabled": True}

        def exec(self):
            return True

    monkeypatch.setattr(settings_dialog, "SourceDialog", FakeSourceDialog)
    dialog = SettingsDialog(settings, config)
    dialog.add_button.click()
    assert dialog.source_list.count() == 2
    assert dialog.source_list.item(1).text().startswith("Scope")


def test_unexpected_errors_are_logged_and_shown(app, monkeypatch, tmp_path):
    shown = []
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)  # restored after the test
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: shown.append(args[2]))
    install_error_handler(tmp_path / "app.log")
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    assert "Something went wrong: boom" in shown[0]
    assert str(tmp_path / "app.log") in shown[0]


def test_removing_a_source(app, settings, config):
    dialog = SettingsDialog(settings, config)
    dialog.source_list.setCurrentRow(0)
    dialog.remove_button.click()
    assert dialog.source_list.count() == 0
