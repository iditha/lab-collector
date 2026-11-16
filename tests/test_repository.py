import sqlite3

import pytest

from labcollector.infra.repository import DuplicateRunError
from labcollector.records import Collection, CollectionStatus, FileResult, FileStatus, Run


def test_create_and_get_run(repository):
    run = repository.create_run(Run(name="RUN-1", operator="Dana", sw_baseline="FW 2.1"))
    assert run.id is not None and run.created_at
    assert repository.get_run(run.id) == run


def test_run_names_are_unique_ignoring_case(repository):
    repository.create_run(Run(name="RUN-1", operator="Dana"))
    with pytest.raises(DuplicateRunError):
        repository.create_run(Run(name="run-1", operator="Avi"))


def test_find_run_ignores_case(repository):
    repository.create_run(Run(name="RUN-1", operator="Dana"))
    assert repository.find_run("run-1").name == "RUN-1"
    assert repository.find_run("nope") is None


def test_list_runs_newest_first_and_search(repository):
    repository.create_run(Run(name="Alpha", operator="Dana", location="Lab 1"))
    repository.create_run(Run(name="Beta", operator="Avi", location="Site B"))
    assert [r.name for r in repository.list_runs()] == ["Beta", "Alpha"]
    assert [r.name for r in repository.list_runs("site")] == ["Beta"]
    assert [r.name for r in repository.list_runs("dan")] == ["Alpha"]


def test_update_run_keeps_name(repository):
    run = repository.create_run(Run(name="RUN-1", operator="Dana"))
    run.results = "Peak at 412 nm"
    run.name = "renamed"
    repository.update_run(run)
    saved = repository.get_run(run.id)
    assert saved.results == "Peak at 412 nm"
    assert saved.name == "RUN-1"


def make_collection(run_id, started="2026-11-16T10:00:00"):
    return Collection(
        run_id=run_id,
        started_at=started,
        finished_at=started,
        status=CollectionStatus.PARTIAL,
        folder="D:/out/RUN-1/x",
        messages=["Instrument B: Source folder not found"],
        config_snapshot={"output_root": "D:/out"},
        files=[
            FileResult(
                source="A",
                rule="Logs",
                category="logs",
                status=FileStatus.COPIED,
                source_path="s/a.log",
                dest_path="d/a.log",
                size=10,
                sha256="ab",
            ),
            FileResult(
                source="A",
                rule="Logs",
                category="logs",
                status=FileStatus.MISSING,
                error="expected 2, found 1",
            ),
        ],
    )


def test_save_and_load_collection_with_files(repository, run):
    saved = repository.save_collection(make_collection(run.id))
    loaded = repository.get_collection(saved.id)
    assert loaded == saved
    assert loaded.files[1].status == FileStatus.MISSING


def test_list_collections_newest_first(repository, run):
    repository.save_collection(make_collection(run.id, "2026-11-16T10:00:00"))
    repository.save_collection(make_collection(run.id, "2026-11-16T12:00:00"))
    collections = repository.list_collections(run.id)
    assert [c.started_at for c in collections] == ["2026-11-16T12:00:00", "2026-11-16T10:00:00"]
    assert all(len(c.files) == 2 for c in collections)


def test_collection_must_belong_to_existing_run(repository):
    with pytest.raises(sqlite3.IntegrityError):
        repository.save_collection(make_collection(run_id=999))
