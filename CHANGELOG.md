# Changelog

The version is set in `labcollector/__init__.py` (and `pyproject.toml`). It is shown in the
window title and recorded with every collection, in its report and in the UDP message.

## 1.0.0 (2026-11-17)

First release.

### Runs
- Create and edit runs: name, operator, location, software / baseline, description, results.
- The operator is pre-filled with the Windows user name.
- Run names are unique (ignoring case) and checked for characters Windows doesn't allow.
- Search runs by name, operator or location.

### Collecting
- Several source folders, each with several rules: file-name prefix, extensions, newest N files,
  maximum age, and the number of files expected.
- A preview of what each rule will collect before copying, with rules that fall short marked.
- Copying on a background thread with progress and Cancel.
- Every copy verified: size, SHA-256 checksum, empty files, and content checks by file type.
- Files organized as `<output>\<run>\<date_time>\<category>\`; nothing is ever overwritten.
- Status per file (copied, missing, couldn't copy, corrupt) and per collection (success,
  partial, failed).
- An HTML and JSON report for every collection; every collection is saved, even a failed one.
- A UDP message with the result sent to a remote computer; a failure is only a warning.

### Viewing
- Files tab: collected files grouped by collection and category; open, show in folder, copy
  path.
- History tab: every collection of a run with its report.

### Settings
- Settings dialog for the output folder, sources and rules, and UDP, with a test message.
- Sources can be switched off without deleting them.
- `config.yaml` can also be edited by hand; it is re-read before every collection, and a broken
  file is explained with options to open it or reset it.
- A warning before overwriting changes made to `config.yaml` outside the app.

### Other
- Help → User guide (F1) and Help → About.
- Errors logged to `data\logs\app.log`; unexpected errors shown with a short message.
- Database upgrades (migrations) that keep existing data.
- Windows build (`tools\build.py`) that runs without Python.
