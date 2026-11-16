# Lab Collector

Desktop app (Python 3.12 + PySide6) that collects lab-run output files from several source
folders using configurable rules, copies them into a per-run folder structure, keeps run details
and collection history in SQLite, writes a success / partial / failed report, and sends a UDP
message to a remote PC. It is a take-home assignment: the requirements are in `docs/SPEC.md`.
The author must explain the code and change it live in an interview, so **prefer simple,
readable code over clever or speculative code**.

## Commands

```
.venv\Scripts\python -m labcollector                  # run the app
.venv\Scripts\python -m pytest                        # all tests (UI tests run offscreen)
.venv\Scripts\python -m ruff format .                 # format
.venv\Scripts\python -m ruff check .                  # lint
.venv\Scripts\python tools\make_demo_data.py          # demo sources + data\config.yaml (PARTIAL)
.venv\Scripts\python tools\make_demo_data.py --fixed  # demo where everything succeeds
.venv\Scripts\python tools\udp_listener.py            # print received UDP messages (2nd PC)
.venv\Scripts\python tools\lock_file.py <file>        # lock a file to demo "couldn't copy"
```

## Architecture

Layers, with dependencies pointing down only:

| Layer | Files | Rule |
|---|---|---|
| `ui/` | `main_window`, `run_form`, `details_tab`, `files_tab`, `history_tab`, `collect_dialog`, `report_view`, `worker`, `helpers`, `style.qss` | Shows data and calls services. No business logic. Never touches the database, the network or the config file directly. |
| `services/` | `run_service` (create/edit runs, `run.json`), `collection_service` (`preview()`, `collect()`, `history()`) | Orchestrates core + infra for one use case. No Qt. |
| `core/` | `matcher` (rule filter pipeline), `verifier` (size, SHA-256, content checks), `report` (HTML/JSON report) | Pure logic. No Qt, no database, no network. |
| `infra/` | `config_store` (config.yaml), `repository` (SQLite: the only place with SQL), `udp_notifier` | Wraps one external thing each. |

Shared: `records.py` (Run, Collection, FileResult, statuses: dataclasses), `config_models.py`
(the config.yaml schema: pydantic), `paths.py`, `logging_setup.py`. `__main__.py` builds every
object and passes it in (dependency injection).

Data on disk: `data\config.yaml`, `data\labcollector.db`, `data\logs\app.log` (next to the app).
Collected files: `<output_root>\<run name>\<YYYY-MM-DD_HH-MM-SS>\<category>\<files>`, plus
`report.html` / `report.json` per collection and `run.json` per run.

Key behaviour:
- File statuses: `copied`, `missing`, `copy_failed`, `corrupt`. Collection status: SUCCESS (all
  expected files copied and verified), FAILED (nothing copied or a fatal error), else PARTIAL.
- `collect()` never raises for expected problems and **always saves** the collection, even a
  failed one. Problems become file results or `messages`; a UDP failure is only a warning.
- Collections run in a background `QThread` (`ui/worker.py`); the window is updated only
  through signals.
- `config.yaml` is re-read before every collection, so edits made outside the app are used.

## Conventions

- Type hints everywhere. Docstrings and comments explain *why*, not *what*.
- Records: `@dataclass(kw_only=True)`. Config: pydantic models with `extra="forbid"`.
- Paths are passed in as parameters; only `__main__.py` reads the constants in `paths.py`.
- Specific exceptions only; a broad `except Exception` only at an outermost boundary, logged.
  Expected outcomes (a corrupt file, a failed UDP send) are returned as results, not raised.
  Messages for the user are plain English and say what to do.
- Qt: full enum names (`Qt.AlignmentFlag.AlignCenter`), `@Slot` on methods that receive
  signals from another thread, named constants for stacked-widget pages.
- UI text is English; no special handling for right-to-left text.
- Ruff: line length 100. Run `ruff format` and `ruff check` before committing.
- Tests: pytest with `tmp_path` (never real folders). Test through public behaviour, e.g.
  click a button rather than calling a private method.
- Git: one commit per feature, with its tests; a one-line commit message; stage files by name
  (never `git add -A`); never push unless asked.
- No unused code and no speculative options: add something when a requirement needs it.

## Status

Done: project setup, config and rules, copy + verification, database and history, report,
UDP, main window, run form, collect dialog, Files and History tabs.

Next:
- **Settings dialog**: output folder (folder picker), sources and rules, UDP host/port with a
  "Send test message" button, open / reload config.yaml; saving validates first. Plus an
  `enabled` switch per source, the app version in the window title, report, UDP message and
  each saved collection, a global error handler, and a clear dialog for an invalid config at start.
- **Delivery**: PyInstaller build, `README.md` (install and run), `docs/ARCHITECTURE.md`
  (including "Extending the app"), `docs/USER_GUIDE.md` with screenshots and a Help menu entry,
  `AI_USAGE.md`, `CHANGELOG.md`, git tag `v1.0.0`.

Known limitations: the collect preview lists folders on the UI thread, so an unreachable network
share can freeze it briefly; lines mixing Hebrew and English may display in the wrong order.
