"""Creating, editing and finding runs."""

import json
import logging
from dataclasses import asdict
from pathlib import Path

from labcollector.config_models import folder_name_problem
from labcollector.infra.repository import Repository
from labcollector.records import Run

log = logging.getLogger(__name__)


class RunValidationError(ValueError):
    """The run's details are invalid. The message lists every problem, one per line."""


def validate(run: Run) -> list[str]:
    problems = []
    name_problem = folder_name_problem(run.name)
    if name_problem:
        problems.append(f"Run name {name_problem}.")
    if not run.operator.strip():
        problems.append("Operator is required.")
    return problems


def write_run_info(run: Run, run_folder: Path) -> None:
    """Save the run's details as run.json, so the folder makes sense even without the app."""
    run_folder.mkdir(parents=True, exist_ok=True)
    text = json.dumps(asdict(run), indent=2, ensure_ascii=False)
    (run_folder / "run.json").write_text(text, encoding="utf-8")


class RunService:
    def __init__(self, repository: Repository):
        self._repository = repository

    def create(self, run: Run) -> Run:
        """Raises RunValidationError, or DuplicateRunError if the name is taken."""
        run.name = run.name.strip()
        run.operator = run.operator.strip()
        problems = validate(run)
        if problems:
            raise RunValidationError("\n".join(problems))
        created = self._repository.create_run(run)
        log.info("Created run '%s'", created.name)
        return created

    def update(self, run: Run) -> None:
        """Save edited details and refresh run.json in the run's folders."""
        existing = self._repository.get_run(run.id)
        if existing is None:
            raise RunValidationError("This run no longer exists.")
        if existing.name != run.name:
            raise RunValidationError("A run's name can't be changed: it names the run's folders.")
        problems = validate(run)
        if problems:
            raise RunValidationError("\n".join(problems))
        self._repository.update_run(run)
        for folder in self.run_folders(run):
            try:
                write_run_info(run, folder)
            except OSError as error:  # the details are saved; only the copy in the folder failed
                log.warning("Couldn't update %s: %s", folder / "run.json", error)

    def run_folders(self, run: Run) -> set[Path]:
        """Folders holding this run's collections (more than one if the output folder changed)."""
        collections = self._repository.list_collections(run.id)
        folders = {Path(c.folder).parent for c in collections if c.folder}
        return {folder for folder in folders if folder.is_dir()}

    def get(self, run_id: int) -> Run | None:
        return self._repository.get_run(run_id)

    def find(self, name: str) -> Run | None:
        return self._repository.find_run(name)

    def search(self, text: str = "") -> list[Run]:
        return self._repository.list_runs(text)
