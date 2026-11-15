"""Check that a copied file is complete and readable.

Checks, in order:
1. the copy has the same size as the source
2. the file is not empty
3. the copy has the same SHA-256 checksum as the source
4. for known file types, the content is valid (e.g. a .json parses, a .zip opens)
"""

import hashlib
import json
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_CHUNK = 1024 * 1024  # read 1 MB at a time so big files don't fill memory


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


# --- Content checks by extension: each raises an error if the file is damaged ----

def _check_json(path: Path) -> None:
    json.loads(path.read_text(encoding="utf-8-sig"))


def _check_zip(path: Path) -> None:
    """.zip and Office files (.xlsx, .docx, .pptx), which are zip archives inside."""
    with zipfile.ZipFile(path) as archive:
        damaged = archive.testzip()
    if damaged:
        raise ValueError(f"damaged entry '{damaged}'")


def _starts_with(*signatures: bytes) -> Callable[[Path], None]:
    """Many formats begin with fixed bytes ("magic number"), e.g. every PDF starts with %PDF-."""
    def check(path: Path) -> None:
        with path.open("rb") as file:
            head = file.read(16)
        if not head.startswith(signatures):
            raise ValueError("the file header doesn't match its type")
    return check


CONTENT_CHECKS: dict[str, Callable[[Path], None]] = {
    ".json": _check_json,
    ".zip": _check_zip,
    ".xlsx": _check_zip,
    ".docx": _check_zip,
    ".pptx": _check_zip,
    ".pdf": _starts_with(b"%PDF-"),
    ".png": _starts_with(b"\x89PNG\r\n\x1a\n"),
    ".jpg": _starts_with(b"\xff\xd8\xff"),
    ".jpeg": _starts_with(b"\xff\xd8\xff"),
    ".gif": _starts_with(b"GIF87a", b"GIF89a"),
}


@dataclass(frozen=True)
class Verification:
    ok: bool
    sha256: str | None = None   # checksum of the copy, when it could be computed
    problem: str | None = None  # what's wrong, written for the user


def content_problem(path: Path) -> str | None:
    """Why the file's content is invalid for its type, or None if fine / type not checked."""
    check = CONTENT_CHECKS.get(path.suffix.lower())
    if check is None:
        return None
    try:
        check(path)
    except (ValueError, zipfile.BadZipFile, EOFError) as error:
        return f"not a valid {path.suffix.lower()} file ({error})"
    return None


def verify_copy(source: Path, copy: Path) -> Verification:
    """Compare ``copy`` with ``source`` and check the copy's content."""
    try:
        size = copy.stat().st_size
        source_size = source.stat().st_size
        if size != source_size:
            return Verification(False, problem=f"size mismatch: source {source_size} bytes, copy {size} bytes")
        if size == 0:
            return Verification(False, problem="the file is empty (0 bytes)")

        checksum = sha256_of(copy)
        if checksum != sha256_of(source):
            return Verification(False, checksum, "the copy differs from the source (checksum mismatch); "
                                                 "the file may have changed while it was being copied")

        problem = content_problem(copy)
        if problem:
            return Verification(False, checksum, problem)
    except OSError as error:
        return Verification(False, problem=f"couldn't read the file: {error.strerror or error}")

    return Verification(True, checksum)
