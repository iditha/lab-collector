"""Lock a file (Windows) so other programs can't read it, to demo a "couldn't copy" error.

    python tools/lock_file.py demo/sources/ControlPC/syslog_2.txt

While it's locked, run a collection: that file is reported as "Couldn't copy".
Press Enter to release the lock.
"""

import msvcrt
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1])
    size = path.stat().st_size
    with path.open("rb") as file:
        msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, size)  # lock bytes 0..size
        input(f"Locked {path}. Press Enter to unlock...")
        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, size)
    print("Unlocked.")


if __name__ == "__main__":
    main()
