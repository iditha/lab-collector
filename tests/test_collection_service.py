import json
import os
import shutil
import socket
from pathlib import Path

import pytest

from labcollector.config_models import AppConfig, Rule, Source, UdpSettings
from labcollector.records import CollectionStatus, FileStatus
from labcollector.services.collection_service import CollectionService, free_path, preview


@pytest.fixture
def sources(tmp_path):
    """Two source folders with a few files each."""
    a = tmp_path / "src" / "A"
    b = tmp_path / "src" / "B"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "MEAS_1.csv").write_text("1")
    (a / "MEAS_2.csv").write_text("2")
    (a / "data.json").write_text('{"ok": true}')
    (b / "log.txt").write_text("hello")
    return tmp_path / "src"


def make_config(tmp_path, sources, *rules_by_source, udp=None):
    names = ["A", "B"]
    return AppConfig(
        output_root=str(tmp_path / "out"),
        udp=udp or UdpSettings(enabled=False),
        sources=[
            Source(name=names[i], path=str(sources / names[i]), rules=rules)
            for i, rules in enumerate(rules_by_source)
        ],
    )


def collect(repository, run, config, **kwargs):
    return CollectionService(repository).collect(run, config, **kwargs)


def test_success_copies_into_category_folders(repository, run, tmp_path, sources):
    config = make_config(
        tmp_path,
        sources,
        [Rule(name="Meas", category="measurements", prefix="MEAS_", expected=2)],
        [Rule(name="Logs", category="logs", extensions=[".txt"])],
    )
    collection = collect(repository, run, config)

    assert collection.status == CollectionStatus.SUCCESS
    folder = Path(collection.folder)
    assert folder.parent == tmp_path / "out" / "RUN-1"
    assert sorted(p.name for p in (folder / "measurements").iterdir()) == [
        "MEAS_1.csv",
        "MEAS_2.csv",
    ]
    assert (folder / "logs" / "log.txt").read_text() == "hello"
    assert all(f.sha256 for f in collection.files)


def test_reports_run_json_and_history_are_written(repository, run, tmp_path, sources):
    config = make_config(tmp_path, sources, [Rule(name="Meas", category="m", prefix="MEAS_")])
    collection = collect(repository, run, config)
    folder = Path(collection.folder)

    assert "Collection succeeded" in (folder / "report.html").read_text(encoding="utf-8")
    assert (
        json.loads((folder / "report.json").read_text(encoding="utf-8"))["summary"]["copied"] == 2
    )
    assert (
        json.loads((folder.parent / "run.json").read_text(encoding="utf-8"))["operator"] == "Dana"
    )
    assert repository.list_collections(run.id)[0].id == collection.id


def test_fewer_files_than_expected_is_partial(repository, run, tmp_path, sources):
    config = make_config(
        tmp_path, sources, [Rule(name="Meas", category="m", prefix="MEAS_", expected=3)]
    )
    collection = collect(repository, run, config)

    assert collection.status == CollectionStatus.PARTIAL
    missing = [f for f in collection.files if f.status == FileStatus.MISSING]
    assert len(missing) == 1
    assert missing[0].error == "expected 3 file(s), found 2"


def test_corrupt_file_is_reported(repository, run, tmp_path, sources):
    (sources / "A" / "data.json").write_text('{"cut')
    config = make_config(tmp_path, sources, [Rule(name="Json", category="j", extensions=[".json"])])
    collection = collect(repository, run, config)

    assert collection.status == CollectionStatus.FAILED  # its only file is corrupt
    assert collection.files[0].status == FileStatus.CORRUPT
    assert "not a valid .json" in collection.files[0].error
    assert Path(collection.files[0].dest_path).exists()  # kept, so it can be inspected


def test_missing_source_folder(repository, run, tmp_path, sources):
    shutil.rmtree(sources / "B")
    config = make_config(
        tmp_path,
        sources,
        [Rule(name="Meas", category="m", prefix="MEAS_")],
        [Rule(name="Logs", category="logs")],
    )
    collection = collect(repository, run, config)

    assert collection.status == CollectionStatus.PARTIAL
    assert any("B: Source folder not found" in m for m in collection.messages)
    assert [f.status for f in collection.files if f.source == "B"] == [FileStatus.MISSING]


def test_nothing_found_fails(repository, run, tmp_path, sources):
    config = make_config(tmp_path, sources, [Rule(name="None", category="n", prefix="ZZZ")])
    assert collect(repository, run, config).status == CollectionStatus.FAILED


def test_no_sources_configured_fails_without_folder(repository, run, tmp_path):
    collection = collect(repository, run, AppConfig(output_root=str(tmp_path / "out")))
    assert collection.status == CollectionStatus.FAILED
    assert "No source folders" in collection.messages[0]
    assert collection.folder == ""
    assert repository.get_collection(collection.id) is not None  # still in history


def test_same_name_from_two_sources_is_kept_twice(repository, run, tmp_path, sources):
    (sources / "B" / "log.txt").rename(sources / "B" / "MEAS_1.csv")
    rule = Rule(name="Meas", category="m", prefix="MEAS_")
    collection = collect(repository, run, make_config(tmp_path, sources, [rule], [rule]))
    names = sorted(Path(f.dest_path).name for f in collection.files)
    assert names == ["MEAS_1 (2).csv", "MEAS_1.csv", "MEAS_2.csv"]


def test_copy_failure_is_reported(repository, run, tmp_path, sources, monkeypatch):
    def locked(src, dst):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(shutil, "copy2", locked)
    config = make_config(tmp_path, sources, [Rule(name="Meas", category="m", prefix="MEAS_")])
    collection = collect(repository, run, config)

    assert {f.status for f in collection.files} == {FileStatus.COPY_FAILED}
    assert "locked" in collection.files[0].error


def test_cancel_stops_and_is_not_success(repository, run, tmp_path, sources):
    config = make_config(tmp_path, sources, [Rule(name="Meas", category="m", prefix="MEAS_")])
    calls = iter([False, True])  # allow the first file, then cancel
    collection = collect(repository, run, config, should_cancel=lambda: next(calls))

    assert len(collection.files) == 1
    assert collection.status == CollectionStatus.PARTIAL
    assert any("Cancelled" in m for m in collection.messages)


def test_progress_is_reported(repository, run, tmp_path, sources):
    config = make_config(tmp_path, sources, [Rule(name="Meas", category="m", prefix="MEAS_")])
    seen = []
    collect(repository, run, config, progress=lambda done, total, msg: seen.append((done, total)))
    assert seen == [(0, 2), (1, 2), (2, 2)]


def test_udp_message_is_sent(repository, run, tmp_path, sources):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))  # port 0 = any free port
        receiver.settimeout(2)
        port = receiver.getsockname()[1]
        udp = UdpSettings(host="127.0.0.1", port=port)
        config = make_config(
            tmp_path, sources, [Rule(name="Meas", category="m", prefix="MEAS_")], udp=udp
        )

        collection = collect(repository, run, config)
        message = json.loads(receiver.recv(65535))

    assert collection.udp_status == f"sent to 127.0.0.1:{port}"
    assert message["run"] == "RUN-1" and message["status"] == "success"


def test_preview_copies_nothing(tmp_path, sources):
    config = make_config(
        tmp_path, sources, [Rule(name="Meas", category="m", prefix="MEAS_", newest=1)]
    )
    os.utime(sources / "A" / "MEAS_1.csv", (0, 0))  # make MEAS_1 old
    plans = preview(config)
    assert [f.path.name for f in plans[0].files] == ["MEAS_2.csv"]
    assert not (tmp_path / "out").exists()


def test_free_path(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "a (2).txt").write_text("x")
    assert free_path(tmp_path / "a.txt").name == "a (3).txt"
    assert free_path(tmp_path / "b.txt").name == "b.txt"


def test_run_json_write_failure_is_reported_but_not_fatal(repository, run, tmp_path, sources):
    # A folder named run.json where the file should go makes writing it fail.
    (tmp_path / "out" / run.name / "run.json").mkdir(parents=True)
    config = make_config(tmp_path, sources, [Rule(name="Meas", category="m", prefix="MEAS_")])
    collection = collect(repository, run, config)

    assert collection.status == CollectionStatus.SUCCESS  # the files themselves were fine
    assert any("Couldn't write run.json" in m for m in collection.messages)
    assert repository.get_collection(collection.id) is not None  # still saved to history
