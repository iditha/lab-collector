"""Stores runs and collection history in a SQLite database.

SQLite is a database in a single file, built into Python: no server to install.
Each method opens its own short connection, so the repository can be used from the
UI thread and from the background collection thread without sharing a connection.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from labcollector.records import Collection, CollectionStatus, FileResult, FileStatus, Run

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,  -- unique, ignoring upper/lower case
    operator    TEXT NOT NULL,
    location    TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    results     TEXT NOT NULL DEFAULT '',
    sw_baseline TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collections (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    started_at      TEXT NOT NULL,
    finished_at     TEXT NOT NULL,
    status          TEXT NOT NULL,
    folder          TEXT NOT NULL,
    udp_status      TEXT NOT NULL DEFAULT '',
    messages        TEXT NOT NULL DEFAULT '[]',  -- JSON list
    config_snapshot TEXT NOT NULL DEFAULT '{}'   -- JSON object
);

CREATE TABLE IF NOT EXISTS collected_files (
    id            INTEGER PRIMARY KEY,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    source        TEXT NOT NULL,
    rule          TEXT NOT NULL,
    category      TEXT NOT NULL,
    status        TEXT NOT NULL,
    source_path   TEXT NOT NULL DEFAULT '',
    dest_path     TEXT NOT NULL DEFAULT '',
    size          INTEGER,
    sha256        TEXT,
    error         TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_collections_run ON collections(run_id);
CREATE INDEX IF NOT EXISTS idx_files_collection ON collected_files(collection_id);
"""

# Changes to the tables after the first version. SCHEMA above is never edited; each later
# change is added here instead, so existing databases are upgraded without losing data.
# The database's "user_version" counts how many of these have been applied.
MIGRATIONS = [
    # 1: remember which version of the app made each collection
    "ALTER TABLE collections ADD COLUMN app_version TEXT NOT NULL DEFAULT ''",
]

# Column names, used to build the INSERT/UPDATE statements below. Building SQL with
# f-strings is safe here because these are fixed constants; every *value* is passed
# separately as a "?" parameter, which is what prevents SQL injection.
RUN_FIELDS = ("name", "operator", "location", "description", "results", "sw_baseline")
FILE_FIELDS = (
    "source",
    "rule",
    "category",
    "status",
    "source_path",
    "dest_path",
    "size",
    "sha256",
    "error",
)


class DuplicateRunError(Exception):
    """A run with this name already exists."""


class Repository:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            applied = conn.execute("PRAGMA user_version").fetchone()[0]
        for number, statement in enumerate(MIGRATIONS[applied:], start=applied + 1):
            self._apply_migration(number, statement)

    def _apply_migration(self, number: int, statement: str) -> None:
        """Apply one migration and record its number together, in one transaction.

        Python's sqlite3 would otherwise commit ALTER TABLE on its own. A crash between the
        change and the version number would then leave the database half-upgraded, and the
        next start would fail trying to add the same column again.
        """
        with self._connect() as conn:
            conn.execute("BEGIN")
            conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {number}")  # a number we control, not input

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row  # rows behave like dicts: row["name"]
        conn.execute("PRAGMA foreign_keys = ON")  # SQLite leaves this off by default
        try:
            with conn:  # commits on success, rolls back if an exception escapes
                yield conn
        finally:
            conn.close()

    # --- Runs ---------------------------------------------------------------------

    def create_run(self, run: Run) -> Run:
        created_at = datetime.now().isoformat(timespec="seconds")
        columns = ", ".join(RUN_FIELDS)
        placeholders = ", ".join("?" * len(RUN_FIELDS))
        values = [getattr(run, field) for field in RUN_FIELDS]
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    f"INSERT INTO runs ({columns}, created_at) VALUES ({placeholders}, ?)",
                    [*values, created_at],
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateRunError(f"A run named '{run.name}' already exists.") from error
        run.id = cursor.lastrowid
        run.created_at = created_at
        return run

    def update_run(self, run: Run) -> None:
        """Save changed details. The name isn't updated: it names the run's folders."""
        fields = [field for field in RUN_FIELDS if field != "name"]
        assignments = ", ".join(f"{field} = ?" for field in fields)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE runs SET {assignments} WHERE id = ?",
                [*(getattr(run, field) for field in fields), run.id],
            )

    def get_run(self, run_id: int) -> Run | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", [run_id]).fetchone()
        return _row_to_run(row) if row else None

    def find_run(self, name: str) -> Run | None:
        """Find a run by name, ignoring upper/lower case."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE name = ?", [name]).fetchone()
        return _row_to_run(row) if row else None

    def list_runs(self, search: str = "") -> list[Run]:
        """Newest first. ``search`` matches part of the name, operator or location."""
        pattern = f"%{search}%"
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs WHERE name LIKE ? OR operator LIKE ? OR location LIKE ? "
                "ORDER BY created_at DESC, id DESC",
                [pattern, pattern, pattern],
            ).fetchall()
        return [_row_to_run(row) for row in rows]

    # --- Collections ----------------------------------------------------------------

    def save_collection(self, collection: Collection) -> Collection:
        """Save a collection and all its file results in one transaction."""
        file_columns = ", ".join(FILE_FIELDS)
        file_placeholders = ", ".join("?" * len(FILE_FIELDS))
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO collections (run_id, started_at, finished_at, status, folder, "
                "udp_status, app_version, messages, config_snapshot) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    collection.run_id,
                    collection.started_at,
                    collection.finished_at,
                    collection.status,
                    collection.folder,
                    collection.udp_status,
                    collection.app_version,
                    json.dumps(collection.messages, ensure_ascii=False),
                    json.dumps(collection.config_snapshot, ensure_ascii=False),
                ],
            )
            collection.id = cursor.lastrowid
            conn.executemany(
                f"INSERT INTO collected_files (collection_id, {file_columns}) "
                f"VALUES (?, {file_placeholders})",
                [
                    [collection.id, *(getattr(file, field) for field in FILE_FIELDS)]
                    for file in collection.files
                ],
            )
        return collection

    def list_collections(self, run_id: int) -> list[Collection]:
        """All collections of a run, newest first, each with its file results."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM collections WHERE run_id = ? ORDER BY started_at DESC, id DESC",
                [run_id],
            ).fetchall()
            file_rows = conn.execute(
                "SELECT * FROM collected_files WHERE collection_id IN "
                "(SELECT id FROM collections WHERE run_id = ?) ORDER BY id",
                [run_id],
            ).fetchall()
        files_by_collection: dict[int, list[FileResult]] = {}
        for row in file_rows:
            files_by_collection.setdefault(row["collection_id"], []).append(_row_to_file(row))
        return [_row_to_collection(row, files_by_collection.get(row["id"], [])) for row in rows]

    def get_collection(self, collection_id: int) -> Collection | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM collections WHERE id = ?", [collection_id]).fetchone()
            if row is None:
                return None
            file_rows = conn.execute(
                "SELECT * FROM collected_files WHERE collection_id = ? ORDER BY id",
                [collection_id],
            ).fetchall()
        return _row_to_collection(row, [_row_to_file(file_row) for file_row in file_rows])


# --- Turning database rows back into records ----------------------------------------


def _row_to_run(row: sqlite3.Row) -> Run:
    values = {field: row[field] for field in RUN_FIELDS}
    return Run(**values, id=row["id"], created_at=row["created_at"])


def _row_to_file(row: sqlite3.Row) -> FileResult:
    values = {field: row[field] for field in FILE_FIELDS}
    values["status"] = FileStatus(values["status"])
    return FileResult(**values)


def _row_to_collection(row: sqlite3.Row, files: list[FileResult]) -> Collection:
    return Collection(
        id=row["id"],
        run_id=row["run_id"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        status=CollectionStatus(row["status"]),
        folder=row["folder"],
        udp_status=row["udp_status"],
        app_version=row["app_version"],
        messages=json.loads(row["messages"]),
        config_snapshot=json.loads(row["config_snapshot"]),
        files=files,
    )
