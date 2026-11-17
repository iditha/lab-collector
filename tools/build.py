"""Build dist\\LabCollector\\LabCollector.exe: a folder that runs on Windows without Python.

    .venv\\Scripts\\python tools\\build.py

Copy the whole dist\\LabCollector folder to another computer and run LabCollector.exe there.
The app keeps its data (config, database, logs) in a "data" folder next to the exe.
"""

from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    PyInstaller.__main__.run(
        [
            str(ROOT / "labcollector" / "__main__.py"),
            "--name=LabCollector",
            "--windowed",  # no console window behind the app
            "--noconfirm",  # replace the previous build without asking
            "--clean",
            f"--paths={ROOT}",  # so "import labcollector" works while bundling
            f"--distpath={ROOT / 'dist'}",
            f"--workpath={ROOT / 'build'}",
            f"--specpath={ROOT / 'build'}",
            # Files the app reads at run time: (source, folder inside the bundle)
            f"--add-data={ROOT / 'labcollector' / 'ui' / 'style.qss'};labcollector/ui",
            f"--add-data={ROOT / 'docs' / 'USER_GUIDE.md'};docs",
            f"--add-data={ROOT / 'docs' / 'images'};docs/images",
        ]
    )


if __name__ == "__main__":
    main()
