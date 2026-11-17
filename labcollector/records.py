"""Records the app creates and stores: runs, and the result of each collection.

These are plain dataclasses, not pydantic models: the app builds them itself, so
there is no hand-written input to validate. infra/repository.py saves them in SQLite.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class FileStatus(StrEnum):
    COPIED = "copied"  # copied and verified
    MISSING = "missing"  # expected but not found, or source folder unreachable
    COPY_FAILED = "copy_failed"  # found but couldn't be copied (locked, access denied...)
    CORRUPT = "corrupt"  # copied, but failed verification


class CollectionStatus(StrEnum):
    SUCCESS = "success"  # every expected file was collected and verified
    PARTIAL = "partial"  # some files collected, some problems
    FAILED = "failed"  # nothing collected, or a fatal error


@dataclass(kw_only=True)
class Run:
    """A lab run: the details the user enters. Its files come from collections."""

    name: str
    operator: str
    location: str = ""
    description: str = ""
    results: str = ""
    sw_baseline: str = ""  # software versions / baseline used for the run
    id: int | None = None  # set by the database
    created_at: str = ""  # ISO date-time, set by the database layer


@dataclass(kw_only=True)
class FileResult:
    """What happened to one file (or one missing file) in a collection."""

    source: str  # source name from the config
    rule: str
    category: str
    status: FileStatus
    source_path: str = ""
    dest_path: str = ""
    size: int | None = None
    sha256: str | None = None
    error: str = ""  # explanation for the user when status isn't COPIED


@dataclass(kw_only=True)
class Collection:
    """One collection operation for a run: when, the outcome, and every file's result."""

    run_id: int
    started_at: str
    finished_at: str = ""
    status: CollectionStatus = CollectionStatus.FAILED
    folder: str = ""  # where this collection's files were copied
    files: list[FileResult] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)  # problems not tied to one file
    udp_status: str = ""
    app_version: str = ""  # which version of Lab Collector made this collection
    config_snapshot: dict = field(default_factory=dict)  # the config used, for traceability
    id: int | None = None

    def count(self, status: FileStatus) -> int:
        return sum(1 for f in self.files if f.status == status)
