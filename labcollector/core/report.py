"""Builds the summary report of a collection: HTML for people, JSON for programs.

The report answers, at a glance: did it fully succeed, were all expected files
collected, and if not, which files have which problem and why.
"""

import html
import json
import os
from dataclasses import asdict

from labcollector.records import Collection, CollectionStatus, FileResult, FileStatus, Run

TITLES = {
    CollectionStatus.SUCCESS: "Collection succeeded",
    CollectionStatus.PARTIAL: "Collection partly succeeded",
    CollectionStatus.FAILED: "Collection failed",
}
COLORS = {  # background, text
    CollectionStatus.SUCCESS: ("#e6f4ea", "#1e6b34"),
    CollectionStatus.PARTIAL: ("#fff4e0", "#8a5300"),
    CollectionStatus.FAILED: ("#fdecea", "#a1261b"),
}
PROBLEM_LABELS = {
    FileStatus.MISSING: "Missing",
    FileStatus.COPY_FAILED: "Couldn't copy",
    FileStatus.CORRUPT: "Corrupt or unreadable",
}


def summary(collection: Collection) -> dict[str, int]:
    return {
        "copied": collection.count(FileStatus.COPIED),
        "missing": collection.count(FileStatus.MISSING),
        "copy_failed": collection.count(FileStatus.COPY_FAILED),
        "corrupt": collection.count(FileStatus.CORRUPT),
        "total": len(collection.files),
    }


def headline(collection: Collection) -> str:
    """One sentence that explains the status."""
    counts = summary(collection)
    problems = counts["total"] - counts["copied"]
    if collection.status == CollectionStatus.SUCCESS:
        return f"All {_files(counts['copied'])} collected and verified."
    if collection.status == CollectionStatus.PARTIAL:
        verb = "needs" if problems == 1 else "need"
        return f"{_files(counts['copied'])} collected, {_files(problems)} {verb} attention."
    if counts["copied"] == 0:
        return "No files were collected."
    return "The collection stopped because of an error."


def to_json(collection: Collection, run: Run) -> str:
    data = {
        "run": asdict(run),
        "collection": {
            "started_at": collection.started_at,
            "finished_at": collection.finished_at,
            "status": collection.status,
            "headline": headline(collection),
            "folder": collection.folder,
            "udp_status": collection.udp_status,
            "app_version": collection.app_version,
            "messages": collection.messages,
        },
        "summary": summary(collection),
        "files": [asdict(file) for file in collection.files],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def to_html(collection: Collection, run: Run) -> str:
    background, color = COLORS[collection.status]
    counts = summary(collection)
    problems = [f for f in collection.files if f.status != FileStatus.COPIED]
    copied = [f for f in collection.files if f.status == FileStatus.COPIED]

    parts = [
        f"<div class='banner' style='background:{background};color:{color}'>"
        f"<h1>{TITLES[collection.status]}</h1><p>{_e(headline(collection))}</p></div>",
        f"<p class='meta'>Run <b dir='auto'>{_e(run.name)}</b> &middot; "
        f"started {_e(_readable(collection.started_at))} &middot; "
        f"finished {_e(_readable(collection.finished_at))}</p>",
        _tiles(counts),
    ]

    if problems:
        rows = "".join(
            f"<tr><td class='bad'>{PROBLEM_LABELS[f.status]}</td>"
            f"<td dir='auto'>{_e(f.source)} / {_e(f.rule)}</td>"
            f"<td dir='auto'>{_e(os.path.basename(f.source_path)) or '&ndash;'}</td>"
            f"<td dir='auto'>{_e(f.error)}</td></tr>"
            for f in problems
        )
        parts.append(
            "<h2>Problems</h2><table><tr><th>Problem</th><th>Source / rule</th>"
            f"<th>File</th><th>Details</th></tr>{rows}</table>"
        )

    if collection.messages:
        items = "".join(f"<li dir='auto'>{_e(m)}</li>" for m in collection.messages)
        parts.append(f"<h2>Messages</h2><ul>{items}</ul>")

    if copied:
        parts.append("<h2>Collected files</h2>")
        for category in sorted({f.category for f in copied}):
            rows = "".join(
                _file_row(f, collection.folder) for f in copied if f.category == category
            )
            parts.append(
                f"<h3>{_e(category)}</h3><table><tr><th>File</th><th>Source / rule</th>"
                f"<th>Size</th></tr>{rows}</table>"
            )

    parts.append(_run_details(run, collection))
    body = "\n".join(parts)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Collection report: {_e(run.name)}</title><style>{_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )


# --- Pieces of the HTML page ----------------------------------------------------


def _e(text: object) -> str:
    """Escape text so names like 'a<b' can't break the page."""
    return html.escape(str(text))


def _tiles(counts: dict[str, int]) -> str:
    tiles = [
        ("Collected", counts["copied"]),
        ("Missing", counts["missing"]),
        ("Couldn't copy", counts["copy_failed"]),
        ("Corrupt", counts["corrupt"]),
    ]
    cells = "".join(
        f"<td class='tile'><div class='num'>{n}</div><div>{label}</div></td>" for label, n in tiles
    )
    return f"<table class='tiles'><tr>{cells}</tr></table>"


def _file_row(file: FileResult, collection_folder: str) -> str:
    link = os.path.relpath(file.dest_path, collection_folder).replace("\\", "/")
    name = os.path.basename(file.dest_path)
    return (
        f"<tr><td dir='auto'><a href='{_e(link)}'>{_e(name)}</a></td>"
        f"<td dir='auto'>{_e(file.source)} / {_e(file.rule)}</td>"
        f"<td>{human_size(file.size)}</td></tr>"
    )


def _run_details(run: Run, collection: Collection) -> str:
    fields = [
        ("Operator", run.operator),
        ("Location", run.location),
        ("Software / baseline", run.sw_baseline),
        ("Description", run.description),
        ("Results", run.results),
        ("Output folder", collection.folder),
        ("UDP message", collection.udp_status),
        (
            "Collected by",
            f"Lab Collector {collection.app_version}" if collection.app_version else "",
        ),
    ]
    rows = "".join(
        f"<tr><th>{label}</th><td dir='auto' class='text'>{_e(value)}</td></tr>"
        for label, value in fields
        if value
    )
    return f"<h2>Run details</h2><table class='details'>{rows}</table>"


def human_size(size: int | None) -> str:
    if size is None:
        return "–"  # a plain dash character: works in HTML and in the UI
    if size < 1024:
        return f"{size} bytes"
    value = size / 1024
    for unit in ("KB", "MB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _readable(iso_time: str) -> str:
    """'2026-11-16T15:05:04' -> '2026-11-16 15:05:04'."""
    return iso_time.replace("T", " ")


def _files(count: int) -> str:
    return "1 file" if count == 1 else f"{count} files"


_CSS = """
body { font-family: 'Segoe UI', Arial, sans-serif; color: #1f2328;
       margin: 24px; max-width: 1000px; }
.banner { padding: 12px 16px; border-radius: 6px; }
.banner h1 { margin: 0 0 4px 0; font-size: 20px; }
.banner p { margin: 0; }
.meta { color: #59636e; }
h2 { font-size: 16px; margin-top: 24px; border-bottom: 1px solid #d1d9e0; padding-bottom: 4px; }
h3 { font-size: 14px; margin-bottom: 4px; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 4px 8px; vertical-align: top;
         border-bottom: 1px solid #eef1f4; }
th { color: #59636e; font-weight: 600; }
.tiles td { border: 1px solid #d1d9e0; text-align: center; padding: 8px; width: 25%; }
.num { font-size: 22px; font-weight: 600; }
.bad { color: #a1261b; font-weight: 600; white-space: nowrap; }
.details th { width: 180px; }
.text { white-space: pre-wrap; }
"""
