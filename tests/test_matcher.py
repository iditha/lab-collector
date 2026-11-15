import os

import pytest

from labcollector.core.matcher import SourceError, list_files, match_rule
from labcollector.models import Rule

NOW = 1_700_000_000.0  # fixed "current time" so the tests never depend on the clock


def make_file(folder, name, minutes_old, content=b"data"):
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    mtime = NOW - minutes_old * 60
    os.utime(path, (mtime, mtime))
    return path


def names(files):
    return [f.path.name for f in files]


@pytest.fixture
def source(tmp_path):
    make_file(tmp_path, "MEAS_001.csv", minutes_old=300)
    make_file(tmp_path, "MEAS_002.csv", minutes_old=60)
    make_file(tmp_path, "meas_003.CSV", minutes_old=10)
    make_file(tmp_path, "MEAS_004.log", minutes_old=5)
    make_file(tmp_path, "other.csv", minutes_old=1)
    return tmp_path


def match(folder, **rule_fields):
    rule = Rule(name="r", category="c", **rule_fields)
    return names(match_rule(list_files(folder), rule, now=NOW))


def test_no_filters_returns_all_files_newest_first(source):
    assert match(source) == ["other.csv", "MEAS_004.log", "meas_003.CSV", "MEAS_002.csv", "MEAS_001.csv"]


def test_prefix_is_not_case_sensitive(source):
    assert match(source, prefix="MEAS_") == ["MEAS_004.log", "meas_003.CSV", "MEAS_002.csv", "MEAS_001.csv"]


def test_extension_is_not_case_sensitive(source):
    assert match(source, extensions=["csv"]) == ["other.csv", "meas_003.CSV", "MEAS_002.csv", "MEAS_001.csv"]


def test_extension_with_two_dots(tmp_path):
    make_file(tmp_path, "backup.tar.gz", minutes_old=1)
    make_file(tmp_path, "notes.gz", minutes_old=1)
    assert match(tmp_path, extensions=[".tar.gz"]) == ["backup.tar.gz"]


def test_max_age_keeps_recent_files_only(source):
    assert match(source, max_age_minutes=30) == ["other.csv", "MEAS_004.log", "meas_003.CSV"]


def test_newest_keeps_n_most_recent(source):
    assert match(source, newest=2) == ["other.csv", "MEAS_004.log"]


def test_rules_combine(source):
    assert match(source, prefix="meas_", extensions=[".csv"], newest=2) == ["meas_003.CSV", "MEAS_002.csv"]


def test_no_match_returns_empty_list(source):
    assert match(source, prefix="NOPE") == []


def test_empty_folder(tmp_path):
    assert match(tmp_path) == []


def test_missing_folder_raises_source_error(tmp_path):
    with pytest.raises(SourceError, match="not found"):
        list_files(tmp_path / "missing")


def test_subfolders_only_scanned_when_recursive(tmp_path):
    make_file(tmp_path, "top.csv", minutes_old=1)
    make_file(tmp_path, "sub/inner.csv", minutes_old=1)
    assert sorted(names(list_files(tmp_path))) == ["top.csv"]
    assert sorted(names(list_files(tmp_path, recursive=True))) == ["inner.csv", "top.csv"]
