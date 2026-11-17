"""Where the app lives on disk and where it keeps its data (config, database, logs).

Only the entry point / UI should read these constants; everything else receives
paths as parameters, so tests can use temporary folders.
"""

import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent

if getattr(sys, "frozen", False):  # running as LabCollector.exe (PyInstaller)
    APP_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(sys._MEIPASS)  # files bundled with the exe (see tools/build.py)
else:  # running from source
    APP_DIR = PACKAGE_DIR.parent
    BUNDLE_DIR = APP_DIR

RESOURCE_DIR = BUNDLE_DIR / "labcollector"
USER_GUIDE = BUNDLE_DIR / "docs" / "USER_GUIDE.md"

DATA_DIR = APP_DIR / "data"
CONFIG_PATH = DATA_DIR / "config.yaml"
DB_PATH = DATA_DIR / "labcollector.db"
LOG_DIR = DATA_DIR / "logs"
DEFAULT_OUTPUT_ROOT = APP_DIR / "collected"
