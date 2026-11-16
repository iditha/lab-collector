"""Runs a collection: find files, copy them, verify them, and record the outcome.

    preview()  which files each rule would collect right now (nothing is copied)
    collect()  copy + verify each file -> decide the status -> send the UDP message
               -> write report.html / report.json -> save to the history database

Output layout:  <output_root>/<run name>/<YYYY-MM-DD_HH-MM-SS>/<category>/<files>
"""

import contextlib
import errno
import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from labcollector.config_models import AppConfig
from labcollector.core import report
from labcollector.core.matcher import FileInfo, SourceError, list_files, match_rule
from labcollector.core.verifier import verify_copy
from labcollector.infra import udp_notifier
from labcollector.infra.repository import Repository
from labcollector.records import Collection, CollectionStatus, FileResult, FileStatus, Run
from labcollector.services.run_service import write_run_info

log = logging.getLogger(__name__)

type ProgressCallback = Callable[[int, int, str], None]  # (files done, total files, message)
type CancelCheck = Callable[[], bool]  # returns True when the user asked to stop


class FatalCollectionError(Exception):
    """A problem that stops the whole collection, e.g. the output folder can't be created."""


@dataclass(kw_only=True)
class RulePlan:
    """What one rule would collect right now: the result of matching, before copying."""

    source: str
    rule: str
    category: str
    expected: int
    files: list[FileInfo] = field(default_factory=list)
    error: str = ""  # set when the source folder couldn't be read


def preview(config: AppConfig, now: float | None = None) -> list[RulePlan]:
    """Match every rule against its source folder. Each folder is listed only once."""
    plans = []
    for source in config.sources:
        try:
            files = list_files(Path(source.path), source.recursive)
            error = ""
        except SourceError as source_error:
            files, error = [], str(source_error)
        for rule in source.rules:
            matches = match_rule(files, rule, now) if not error else []
            plans.append(
                RulePlan(
                    source=source.name,
                    rule=rule.name,
                    category=rule.category,
                    expected=rule.expected,
                    files=matches,
                    error=error,
                )
            )
    return plans


class CollectionService:
    def __init__(self, repository: Repository):
        self._repository = repository

    def collect(
        self,
        run: Run,
        config: AppConfig,
        progress: ProgressCallback | None = None,
        should_cancel: CancelCheck | None = None,
        now: float | None = None,
    ) -> Collection:
        """Collect files for ``run``. Always returns a saved Collection, even when it failed."""
        progress = progress or (lambda done, total, message: None)
        should_cancel = should_cancel or (lambda: False)
        started = datetime.now()
        collection = Collection(
            run_id=run.id,
            started_at=_timestamp(started),
            config_snapshot=config.model_dump(mode="json"),
        )
        log.info("Collection for run '%s' started", run.name)

        fatal = cancelled = False
        try:
            if not config.sources:
                raise FatalCollectionError(
                    "No source folders are configured. Add them in Settings."
                )
            plans = preview(config, now)
            folder = _create_collection_folder(Path(config.output_root) / run.name, started)
            collection.folder = str(folder)
            _write_run_info_safely(run, collection)
            cancelled = _copy_all(plans, collection, progress, should_cancel)
        except FatalCollectionError as error:
            fatal = True
            collection.messages.append(str(error))
        except Exception as error:  # a bug: record it rather than lose the whole collection
            fatal = True
            log.exception("Unexpected error during collection")
            collection.messages.append(f"Unexpected error: {error}")

        collection.finished_at = _timestamp(datetime.now())
        collection.status = decide_status(collection.files, fatal, cancelled)
        collection.udp_status = self._notify(config, run, collection)
        self._write_reports(run, collection)
        self._repository.save_collection(collection)
        log.info("Collection for run '%s' finished: %s", run.name, collection.status)
        return collection

    def _notify(self, config: AppConfig, run: Run, collection: Collection) -> str:
        """Send the UDP message. A failure is a warning: it doesn't change the status."""
        udp = config.udp
        if not udp.enabled:
            return "disabled"
        payload = {
            "app": "LabCollector",
            "run": run.name,
            "started_at": collection.started_at,
            "status": collection.status,
            "summary": report.summary(collection),
            "folder": collection.folder,
        }
        error = udp_notifier.send(udp.host, udp.port, payload)
        if error:
            log.warning("UDP message not sent: %s", error)
            collection.messages.append(f"UDP message not sent: {error}")
            return f"failed: {error}"
        return f"sent to {udp.host}:{udp.port}"

    def _write_reports(self, run: Run, collection: Collection) -> None:
        if not collection.folder:  # failed before a folder was created
            return
        folder = Path(collection.folder)
        try:
            (folder / "report.html").write_text(report.to_html(collection, run), encoding="utf-8")
            (folder / "report.json").write_text(report.to_json(collection, run), encoding="utf-8")
        except OSError as error:
            log.warning("Couldn't write the report in %s: %s", folder, error)
            collection.messages.append(
                f"Couldn't write the report files: {error.strerror or error}"
            )


# --- Steps of a collection (module-level so they can be tested on their own) --------------


def _copy_all(
    plans: list[RulePlan],
    collection: Collection,
    progress: ProgressCallback,
    should_cancel: CancelCheck,
) -> bool:
    """Copy every planned file into the collection folder. Returns True if the user cancelled."""
    folder = Path(collection.folder)
    total = sum(len(plan.files) for plan in plans)
    done = 0
    for plan in plans:
        if plan.error:
            collection.messages.append(f"{plan.source}: {plan.error}")
        for info in plan.files:
            if should_cancel():
                collection.messages.append("Cancelled before all files were copied.")
                return True
            progress(done, total, f"Copying {info.path.name}")
            collection.files.append(copy_and_verify(info, plan, folder))
            done += 1
        collection.files.extend(missing_results(plan))
    progress(total, total, "Done")
    return False


def copy_and_verify(info: FileInfo, plan: RulePlan, collection_folder: Path) -> FileResult:
    """Copy one file into its category folder, verify the copy, and describe the outcome."""
    result = FileResult(
        source=plan.source,
        rule=plan.rule,
        category=plan.category,
        status=FileStatus.COPY_FAILED,
        source_path=str(info.path),
    )
    target = None
    try:
        target_dir = collection_folder / plan.category
        target_dir.mkdir(exist_ok=True)
        target = free_path(target_dir / info.path.name)
        shutil.copy2(info.path, target)  # copy2 also keeps the original modified time
    except OSError as error:
        _discard(target)
        if error.errno == errno.ENOSPC:
            raise FatalCollectionError("The output disk is full.") from error
        if not info.path.exists():
            result.status = FileStatus.MISSING
            result.error = "the file was deleted or moved before it could be copied"
        elif isinstance(error, PermissionError):
            result.error = "access denied, or the file is locked by another program"
        else:
            result.error = f"copy failed: {error.strerror or error}"
        return result

    verification = verify_copy(info.path, target)
    result.dest_path = str(target)
    result.size = info.size
    result.sha256 = verification.sha256
    if verification.ok:
        result.status = FileStatus.COPIED
    else:
        result.status = FileStatus.CORRUPT
        result.error = verification.problem or ""
    return result


def missing_results(plan: RulePlan) -> list[FileResult]:
    """One MISSING result for each file the rule expected but didn't find."""
    shortfall = plan.expected - len(plan.files)
    reason = plan.error or f"expected {plan.expected} file(s), found {len(plan.files)}"
    return [
        FileResult(
            source=plan.source,
            rule=plan.rule,
            category=plan.category,
            status=FileStatus.MISSING,
            error=reason,
        )
        for _ in range(shortfall)
    ]


def decide_status(files: list[FileResult], fatal: bool, cancelled: bool) -> CollectionStatus:
    copied = sum(1 for f in files if f.status == FileStatus.COPIED)
    if fatal or copied == 0:
        return CollectionStatus.FAILED
    if copied == len(files) and not cancelled:
        return CollectionStatus.SUCCESS
    return CollectionStatus.PARTIAL


def free_path(path: Path) -> Path:
    """``path``, or 'name (2).ext', 'name (3).ext'... if it's taken (same name from two sources)."""
    candidate, number = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        number += 1
    return candidate


def _create_collection_folder(run_folder: Path, started: datetime) -> Path:
    name = started.strftime("%Y-%m-%d_%H-%M-%S")
    folder, number = run_folder / name, 2
    while folder.exists():  # two collections in the same second
        folder = run_folder / f"{name}_{number}"
        number += 1
    try:
        folder.mkdir(parents=True)
    except OSError as error:
        raise FatalCollectionError(
            f"Can't create the output folder {folder}: {error.strerror or error}"
        ) from error
    return folder


def _write_run_info_safely(run: Run, collection: Collection) -> None:
    """Write run.json next to the collection; a failure is only a warning."""
    try:
        write_run_info(run, Path(collection.folder).parent)
    except OSError as error:
        collection.messages.append(f"Couldn't write run.json: {error.strerror or error}")


def _discard(path: Path | None) -> None:
    """Delete a half-written copy, if there is one."""
    if path is not None:
        with contextlib.suppress(OSError):  # best effort: the copy already failed
            path.unlink(missing_ok=True)


def _timestamp(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")
