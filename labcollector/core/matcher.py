"""Find the files a rule selects in a source folder.

A rule runs as a pipeline of small filters. Each filter gets the current list of
files and returns the ones that pass, so the rule types combine naturally:

    all files -> by_prefix -> by_extension -> by_max_age -> newest_first -> matches

To add a new kind of rule, write one filter function and add it to PIPELINE.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from labcollector.config_models import Rule

log = logging.getLogger(__name__)


class SourceError(Exception):
    """A source folder can't be read (missing, not a folder, or no permission)."""


@dataclass(frozen=True)
class FileInfo:
    path: Path
    size: int
    mtime: float  # last modified, in seconds since 1970 (as returned by os.stat)


# Temporary files other programs keep next to open documents; never real lab output.
TEMP_FILE_PREFIXES = (
    "~$",  # Microsoft Office lock file, e.g. ~$report.xlsx while report.xlsx is open
    ".~lock.",  # LibreOffice lock file
)


def is_temporary(name: str) -> bool:
    return name.startswith(TEMP_FILE_PREFIXES)


def list_files(folder: Path, recursive: bool = False) -> list[FileInfo]:
    """All files in ``folder`` (and its subfolders if ``recursive``), except temporary files."""
    if not folder.is_dir():
        raise SourceError(f"Source folder not found or not reachable: {folder}")

    files = []
    try:
        candidates = folder.rglob("*") if recursive else folder.iterdir()
        for path in candidates:
            if is_temporary(path.name):
                continue
            try:
                if not path.is_file():
                    continue
                stat = path.stat()
            except OSError as error:  # one unreadable file shouldn't hide the others
                log.warning("Skipping %s: %s", path, error)
                continue
            files.append(FileInfo(path, stat.st_size, stat.st_mtime))
    except OSError as error:
        raise SourceError(
            f"Can't read source folder {folder}: {error.strerror or error}"
        ) from error
    return files


# --- Filters: (files, rule, now) -> files that pass -----------------------------

type Filter = Callable[[list[FileInfo], Rule, float], list[FileInfo]]


def by_prefix(files: list[FileInfo], rule: Rule, now: float) -> list[FileInfo]:
    if not rule.prefix:
        return files
    prefix = rule.prefix.lower()  # Windows file names are not case-sensitive
    return [f for f in files if f.path.name.lower().startswith(prefix)]


def by_extension(files: list[FileInfo], rule: Rule, now: float) -> list[FileInfo]:
    if not rule.extensions:
        return files
    endings = tuple(rule.extensions)  # endswith() also handles '.tar.gz'
    return [f for f in files if f.path.name.lower().endswith(endings)]


def by_max_age(files: list[FileInfo], rule: Rule, now: float) -> list[FileInfo]:
    if rule.max_age_minutes is None:
        return files
    cutoff = now - rule.max_age_minutes * 60
    return [f for f in files if f.mtime >= cutoff]


def newest_first(files: list[FileInfo], rule: Rule, now: float) -> list[FileInfo]:
    ordered = sorted(files, key=lambda f: f.mtime, reverse=True)
    return ordered[: rule.newest] if rule.newest else ordered


PIPELINE: list[Filter] = [by_prefix, by_extension, by_max_age, newest_first]


def match_rule(files: list[FileInfo], rule: Rule, now: float | None = None) -> list[FileInfo]:
    """Run ``files`` through every filter. ``now`` is a parameter so tests can fix the time."""
    if now is None:
        now = time.time()
    for step in PIPELINE:
        files = step(files, rule, now)
    return files
