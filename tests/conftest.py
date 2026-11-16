"""Shared test fixtures: pytest passes them to any test that names them as a parameter."""

import pytest

from labcollector.infra.repository import Repository
from labcollector.records import Run
from labcollector.services.run_service import RunService


@pytest.fixture
def repository(tmp_path):
    return Repository(tmp_path / "test.db")


@pytest.fixture
def run(repository):
    return RunService(repository).create(Run(name="RUN-1", operator="Dana", location="Lab 2"))
