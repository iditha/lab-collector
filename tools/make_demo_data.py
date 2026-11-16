"""Create demo source folders and a matching config, to show every case in a demo.

    python tools/make_demo_data.py          # with problems: one corrupt file, one missing
    python tools/make_demo_data.py --fixed  # everything present and valid

Creates demo/sources/... and writes data/config.yaml (the old one is kept as
config.yaml.bak). Collected files go to demo/collected/.
"""

import argparse
import io
import os
import shutil
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
SOURCES = DEMO / "sources"

CONFIG = """\
# Demo configuration written by tools/make_demo_data.py
output_root: {output}
udp: {{enabled: true, host: 127.0.0.1, port: 5005}}
sources:
- name: Instrument A
  path: {sources}/InstrumentA
  rules:
  - {{name: Measurements, category: measurements, prefix: MEAS_, extensions: [.csv],
     newest: 3, max_age_minutes: 120, expected: 3}}
  - {{name: Screenshot, category: images, extensions: [.png], newest: 1}}
  - {{name: Summary, category: results, extensions: [.xlsx], newest: 1}}
- name: Control PC
  path: {sources}/ControlPC
  rules:
  - {{name: System logs, category: logs, prefix: syslog, extensions: [.txt], newest: 2,
     expected: 2}}
  - {{name: Results, category: results, extensions: [.json], newest: 2, expected: 2}}
- name: Spectrometer
  path: {sources}/Spectrometer
  rules:
  - {{name: Spectra, category: spectra, extensions: [.spc], newest: 1}}
"""


def write(path: Path, content: bytes, minutes_old: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    mtime = time.time() - minutes_old * 60
    os.utime(path, (mtime, mtime))


def xlsx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>")
    return buffer.getvalue()


def make_sources(fixed: bool) -> None:
    if SOURCES.exists():
        shutil.rmtree(SOURCES)

    a = SOURCES / "InstrumentA"
    write(a / "MEAS_000.csv", b"t,value\n0,0.98\n", minutes_old=3 * 24 * 60)  # too old
    for number, age in [(1, 200), (2, 90), (3, 30), (4, 10)]:
        write(a / f"MEAS_{number:03}.csv", f"t,value\n{number},1.0{number}\n".encode(), age)
    write(a / "screen_00.png", b"\x89PNG\r\n\x1a\n" + bytes(32), minutes_old=60)
    write(a / "screen_01.png", b"\x89PNG\r\n\x1a\n" + bytes(32), minutes_old=5)
    write(a / "summary.xlsx", xlsx_bytes(), minutes_old=5)
    write(a / "~$summary.xlsx", b"lock", minutes_old=1)  # Excel lock file: must be skipped

    c = SOURCES / "ControlPC"
    write(c / "syslog_1.txt", b"boot ok\n", minutes_old=40)
    write(c / "syslog_2.txt", b"run started\nrun finished\n", minutes_old=20)
    write(c / "settings.json", b'{"gain": 4, "mode": "fast"}', minutes_old=50)
    results = b'{"peak": 412.7, "snr": 31.2}' if fixed else b'{"peak": 412.7, "sn'  # cut off
    write(c / "results.json", results, minutes_old=15)

    s = SOURCES / "Spectrometer"
    s.mkdir(parents=True)
    if fixed:
        write(s / "spectrum_001.spc", b"SPC" + bytes(range(64)), minutes_old=25)


def write_config(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        shutil.copy2(config_path, config_path.with_name(config_path.name + ".bak"))
    text = CONFIG.format(output=(DEMO / "collected").as_posix(), sources=SOURCES.as_posix())
    config_path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixed", action="store_true", help="no corrupt or missing files")
    parser.add_argument("--config", type=Path, default=ROOT / "data" / "config.yaml")
    args = parser.parse_args()

    make_sources(args.fixed)
    write_config(args.config)
    print(f"Demo sources: {SOURCES}")
    print(f"Config:       {args.config}")
    if args.fixed:
        print("Expected result: SUCCESS")
    else:
        print("Expected result: PARTIAL (Control PC results.json corrupt, no spectrum file)")


if __name__ == "__main__":
    main()
