"""Shared test fixtures: pytest passes them to any test that names them as a parameter.

pytest loads this file before the test modules, so it's the place for settings
that must exist before anything imports Qt.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # UI tests run without opening windows

import pytest

from labcollector.infra import udp_notifier
from labcollector.infra.repository import Repository
from labcollector.records import Run
from labcollector.services.run_service import RunService


@pytest.fixture
def repository(tmp_path):
    return Repository(tmp_path / "test.db")


@pytest.fixture
def broken_network(monkeypatch):
    """Every UDP send fails, like on a PC with no network. No real network or DNS is used."""

    class BrokenSocket:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def settimeout(self, seconds):
            pass

        def sendto(self, data, address):
            raise OSError(10051, "A socket operation was attempted to an unreachable network")

    monkeypatch.setattr(udp_notifier.socket, "socket", BrokenSocket)


@pytest.fixture
def run(repository):
    return RunService(repository).create(Run(name="RUN-1", operator="Dana", location="Lab 2"))
