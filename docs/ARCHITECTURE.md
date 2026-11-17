# Lab Collector architecture

A Python desktop app with a Qt (PySide6) interface, split into four layers. Each layer uses only
the layers below it.

```
 ui/         Windows and dialogs: shows data and calls services. No business logic; never
   │         touches the database, the network or the config file.
 services/   One per use case: runs, collection, settings. Coordinates core and infra.
   │
   ├──────────────────────────────┐
 core/       Pure logic           infra/      One wrapper per external thing
   matcher   which files a rule     repository     SQLite (the only place with SQL)
             picks                  config_store   config.yaml
   verifier  is the copy correct?   udp_notifier   the UDP message
   report    HTML / JSON report

 Shared: records.py (Run, Collection, FileResult), config_models.py (config.yaml schema)
```

The UI also uses `core/report` directly, to display reports and file statuses: it is pure
presentation logic with no file, database or network access.

`__main__.py` creates every object once and passes it in (dependency injection), so tests can
use temporary folders and a temporary database.

## How a collection works

**Collect now** re-reads `config.yaml`, shows a preview of what each rule will collect, and then
runs `CollectionService.collect()` on a background thread (the window stays responsive; the
thread reports progress through Qt signals):

1. For each rule of each enabled source, the **matcher** picks files:
   prefix → extensions → max age → newest N.
2. Create `<output>\<run name>\<YYYY-MM-DD_HH-MM-SS>\`.
3. Copy each file into its category folder; the **verifier** checks size, SHA-256, that it isn't
   empty, and its content by type (e.g. .json parses, .xlsx opens).
4. Give each file a status (copied, missing, couldn't copy, corrupt) and the collection a
   status (SUCCESS, PARTIAL, FAILED).
5. Send the UDP message.
6. Write `report.html` and `report.json`, and save everything in the database.

## Error handling

Expected problems are results, not crashes. `collect()` never raises for them and always saves
the collection, even a failed one: problems become file statuses or messages in the report. A
UDP failure is only a warning. A broken `config.yaml` is explained with the line or setting that
is wrong. Anything unexpected is logged to `data\logs\app.log` and shown as a short message.

## Data

| What | Where |
|---|---|
| Settings | `data\config.yaml`: written by the app, editable by hand, re-read before each collection |
| Runs and history | `data\labcollector.db` (SQLite): tables `runs`, `collections`, `collected_files` |
| Collected files | `<output>\<run>\<date_time>\<category>\`, plus `report.html/json` and `run.json` |

Each collection also stores a snapshot of the settings it used and the app version. Database
changes are added as migrations, so existing data is kept on upgrade.

## Design decisions

| Decision | Why |
|---|---|
| Layers | Each part has one job, so a change touches one place and can be tested on its own. |
| Python + PySide6 | Quick to write, strong file libraries, a native Windows UI. |
| SQLite | Built into Python, one file, no server. |
| YAML + pydantic | Editable by hand, with a precise error for every wrong value. |
| One shared configuration | The sources describe the lab setup, not a single run. |

## Extending the app

Each change also needs its tests.

- **A new rule type** (e.g. a minimum file size):
  - `config_models.py`: a field in `Rule`
  - `core/matcher.py`: a filter function, added to `PIPELINE`
  - `ui/source_dialog.py`: a column in `RULE_COLUMNS` (and `EMPTY_MEANS_DEFAULT` if it's optional)
  - `infra/config_store.py`: a line in the example in `HEADER`
- **A new content check** (e.g. .xml must parse): a function in `core/verifier.py`, added to
  `CONTENT_CHECKS`.
- **A new run field** (e.g. temperature):
  - `records.py`: a field in `Run`
  - `infra/repository.py`: an `ALTER TABLE runs ADD COLUMN …` in `MIGRATIONS`, the name in
    `RUN_FIELDS`, and a test that upgrades an old database
  - `services/run_service.py`: the name in `TEXT_FIELDS` (spaces are trimmed)
  - `ui/run_form.py`: a widget, a form row, `_fill` and `_save`
  - `ui/details_tab.py`: a line in `FIELDS`
  - `core/report.py`: a line in `_run_details`

  (`run.json` and `report.json` include it automatically.)
