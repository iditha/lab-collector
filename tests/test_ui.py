"""UI tests. Qt runs "offscreen" (set in conftest.py), so no window opens."""

import time

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from labcollector.config_models import AppConfig, Rule, Source, UdpSettings
from labcollector.records import CollectionStatus, Run
from labcollector.services.collection_service import CollectionService
from labcollector.services.run_service import RunService
from labcollector.ui import files_tab, history_tab
from labcollector.ui.collect_dialog import PREVIEW, RESULT, RUNNING, CollectDialog
from labcollector.ui.main_window import EMPTY_PAGE, RUN_PAGE, MainWindow
from labcollector.ui.run_form import RunDialog

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
def make_window(runs, repository, config):
    return lambda: MainWindow(runs, CollectionService(repository), load_config=lambda: config)


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


def test_dialog_shows_every_error_and_stays_open(app, runs):
    dialog = RunDialog(runs)
    dialog.name.setText("bad/name")
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
