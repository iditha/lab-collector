"""UI tests. Qt runs "offscreen" (set in conftest.py), so no window opens."""

import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from labcollector.records import Run
from labcollector.services.run_service import RunService
from labcollector.ui.main_window import EMPTY_PAGE, RUN_PAGE, MainWindow
from labcollector.ui.run_form import RunDialog

SAVE = QDialogButtonBox.StandardButton.Save


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def runs(repository):
    return RunService(repository)


def test_empty_state_when_there_are_no_runs(app, runs):
    window = MainWindow(runs)
    assert window.pages.currentIndex() == EMPTY_PAGE
    assert window.empty_title.text() == "No runs yet"


def test_newest_run_is_selected_and_shown(app, runs):
    runs.create(Run(name="RUN-1", operator="Avi"))
    runs.create(Run(name="RUN-2", operator="Dana", location="Lab 2"))
    window = MainWindow(runs)
    assert window.pages.currentIndex() == RUN_PAGE
    assert window.run_title.text() == "RUN-2"
    assert "Dana" in window.run_subtitle.text()


def test_clicking_another_run_shows_it(app, runs):
    runs.create(Run(name="RUN-1", operator="Avi"))
    runs.create(Run(name="RUN-2", operator="Dana"))
    window = MainWindow(runs)
    window.run_list.setCurrentRow(1)  # the list is newest first, so row 1 is RUN-1
    assert window.run_title.text() == "RUN-1"


def test_search_filters_the_list(app, runs):
    runs.create(Run(name="Alpha", operator="Dana"))
    runs.create(Run(name="Beta", operator="Avi"))
    window = MainWindow(runs)
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
