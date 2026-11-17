import json
import socket

from labcollector.core import report
from labcollector.infra import udp_notifier
from labcollector.records import Collection, CollectionStatus, FileResult, FileStatus, Run

RUN = Run(name="RUN <1>", operator="Dana", results="ok", id=1)


def collection(status, files):
    return Collection(
        run_id=1, started_at="s", finished_at="f", status=status, folder="D:/out/x", files=files
    )


def copied(name):
    return FileResult(
        source="A",
        rule="r",
        category="logs",
        status=FileStatus.COPIED,
        source_path=f"S:/{name}",
        dest_path=f"D:/out/x/logs/{name}",
        size=2048,
        sha256="5e3a9f0c7b21",
    )


def missing():
    return FileResult(
        source="A", rule="r", category="logs", status=FileStatus.MISSING, error="expected 2"
    )


def test_headline_and_summary():
    c = collection(CollectionStatus.PARTIAL, [copied("a.log"), missing()])
    assert report.summary(c) == {
        "copied": 1,
        "missing": 1,
        "copy_failed": 0,
        "corrupt": 0,
        "total": 2,
    }
    assert report.headline(c) == "1 file collected, 1 file needs attention."
    c.files.append(missing())
    assert report.headline(c) == "1 file collected, 2 files need attention."


def test_html_escapes_names_and_links_files():
    page = report.to_html(collection(CollectionStatus.SUCCESS, [copied("a.log")]), RUN)
    assert "RUN &lt;1&gt;" in page and "RUN <1>" not in page
    assert "href='logs/a.log'" in page
    assert "2.0 KB" in page
    assert "5e3a9f0c7b21" not in page  # the checksum is for programs, not for readers


def test_json_report_is_valid():
    data = json.loads(report.to_json(collection(CollectionStatus.SUCCESS, [copied("a.log")]), RUN))
    assert data["collection"]["status"] == "success"
    assert data["files"][0]["status"] == "copied"
    assert data["files"][0]["sha256"] == "5e3a9f0c7b21"


def test_human_size():
    assert report.human_size(500) == "500 bytes"
    assert report.human_size(1536) == "1.5 KB"
    assert report.human_size(5 * 1024**3) == "5.0 GB"


def test_udp_send_and_receive():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2)
        port = receiver.getsockname()[1]
        assert udp_notifier.send("127.0.0.1", port, {"run": "רן"}) is None
        assert json.loads(receiver.recv(1024).decode("utf-8")) == {"run": "רן"}


def test_udp_send_failure_is_returned_not_raised(broken_network):
    error = udp_notifier.send("192.168.1.50", 5005, {})
    assert error == (
        "couldn't send to 192.168.1.50:5005: "
        "A socket operation was attempted to an unreachable network"
    )
