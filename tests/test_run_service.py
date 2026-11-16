import json

import pytest

from labcollector.records import Collection, Run
from labcollector.services.run_service import RunService, RunValidationError


def test_create_trims_and_validates(repository):
    run = RunService(repository).create(Run(name="  RUN-7 ", operator=" Dana "))
    assert (run.name, run.operator) == ("RUN-7", "Dana")


def test_invalid_run_lists_every_problem(repository):
    with pytest.raises(RunValidationError) as error:
        RunService(repository).create(Run(name="a/b", operator=""))
    message = str(error.value)
    assert "Run name must not contain /" in message
    assert "Operator is required" in message


def test_name_cannot_change(repository, run):
    run.name = "Other"
    with pytest.raises(RunValidationError, match="can't be changed"):
        RunService(repository).update(run)


def test_update_refreshes_run_json(repository, run, tmp_path):
    run_folder = tmp_path / "out" / run.name
    (run_folder / "2026-11-16_10-00-00").mkdir(parents=True)
    repository.save_collection(
        Collection(
            run_id=run.id,
            started_at="x",
            finished_at="x",
            folder=str(run_folder / "2026-11-16_10-00-00"),
        )
    )
    run.results = "Looks good"
    RunService(repository).update(run)
    info = json.loads((run_folder / "run.json").read_text(encoding="utf-8"))
    assert info["results"] == "Looks good"
