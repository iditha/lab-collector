"""Application logging: a rotating file in data/logs plus the console."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(log_dir: Path, level: int = logging.INFO) -> Path:
    """Send log records to ``<log_dir>/app.log`` (max 3 x 1 MB) and to stderr.

    Safe to call more than once; handlers are only added the first time.
    Returns the log file path so the UI can offer to open it.
    """
    log_file = log_dir / "app.log"
    root = logging.getLogger()
    if getattr(root, "_labcollector_configured", False):
        return log_file

    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_FORMAT)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    root._labcollector_configured = True
    return log_file
