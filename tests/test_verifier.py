import io
import shutil
import zipfile

from labcollector.core.verifier import verify_copy


def copy_of(tmp_path, name, content):
    source = tmp_path / "src" / name
    source.parent.mkdir(exist_ok=True)
    source.write_bytes(content)
    copy = tmp_path / "dst" / name
    copy.parent.mkdir(exist_ok=True)
    shutil.copy2(source, copy)
    return source, copy


def zip_bytes():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.txt", "hello")
    return buffer.getvalue()


def test_identical_copy_is_ok(tmp_path):
    source, copy = copy_of(tmp_path, "data.log", b"line 1\nline 2\n")
    result = verify_copy(source, copy)
    assert result.ok
    assert len(result.sha256) == 64


def test_size_mismatch(tmp_path):
    source, copy = copy_of(tmp_path, "data.log", b"full content")
    copy.write_bytes(b"cut")
    result = verify_copy(source, copy)
    assert not result.ok and "size mismatch" in result.problem


def test_same_size_different_content(tmp_path):
    source, copy = copy_of(tmp_path, "data.log", b"aaaa")
    copy.write_bytes(b"bbbb")
    result = verify_copy(source, copy)
    assert not result.ok and "checksum" in result.problem


def test_empty_file_is_reported(tmp_path):
    source, copy = copy_of(tmp_path, "data.log", b"")
    result = verify_copy(source, copy)
    assert not result.ok and "empty" in result.problem


def test_valid_and_invalid_json(tmp_path):
    assert verify_copy(*copy_of(tmp_path, "good.json", b'{"a": 1}')).ok
    result = verify_copy(*copy_of(tmp_path, "bad.json", b'{"a": '))
    assert not result.ok and "not a valid .json" in result.problem


def test_valid_and_invalid_zip_based_files(tmp_path):
    assert verify_copy(*copy_of(tmp_path, "good.xlsx", zip_bytes())).ok
    result = verify_copy(*copy_of(tmp_path, "bad.xlsx", b"not a zip at all"))
    assert not result.ok and "not a valid .xlsx" in result.problem


def test_header_must_match_type(tmp_path):
    assert verify_copy(*copy_of(tmp_path, "good.pdf", b"%PDF-1.7 ...")).ok
    result = verify_copy(*copy_of(tmp_path, "bad.png", b"this is text"))
    assert not result.ok and "header" in result.problem


def test_unknown_types_skip_content_check(tmp_path):
    assert verify_copy(*copy_of(tmp_path, "raw.bin", b"\x00\x01anything")).ok


def test_missing_copy_is_reported(tmp_path):
    source, copy = copy_of(tmp_path, "data.log", b"x")
    copy.unlink()
    result = verify_copy(source, copy)
    assert not result.ok and "couldn't read" in result.problem
