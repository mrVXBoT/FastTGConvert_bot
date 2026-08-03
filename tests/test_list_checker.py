"""tests/test_list_checker.py — Comprehensive unit & integration tests for List Checker service.

Tests cover:
  1. Safe path validation (Zip Slip / path traversal protection)
  2. Tdata key extraction & implicit directory detection
  3. Case-insensitivity matching (.SESSION, .Json, phone folders)
  4. Nested Tdata folder handling
  5. Empty / no-match behavior (total=0, output_bytes=None)
  6. Corrupted ZIP archive exception handling
  7. End-to-end integration test with real ZIP files on disk
"""
import io
import zipfile
from pathlib import Path

import pytest

from app.services.list_checker import (
    _extract_tdata_key,
    _is_safe_path,
    compare_archive_files,
    compare_archives,
)


def _create_zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, contents in files.items():
            zf.writestr(path, contents)
    return buf.getvalue()


# ── 1. Safe Path Validation (Zip Slip) ────────────────────────────────────────

def test_is_safe_path():
    assert _is_safe_path("596696702021/D877F783") is True
    assert _is_safe_path("user.json") is True
    assert _is_safe_path("folder/sub/file.txt") is True

    # Vulnerable / Path traversal attempts
    assert _is_safe_path("/etc/passwd") is False
    assert _is_safe_path("../secret.txt") is False
    assert _is_safe_path("596696702021/../../etc/passwd") is False
    assert _is_safe_path("") is False


# ── 2. Tdata Key Extraction ───────────────────────────────────────────────────

def test_extract_tdata_key():
    assert _extract_tdata_key(["596696702021"]) == "596696702021"
    assert _extract_tdata_key(["+596696702021"]) == "596696702021"
    assert _extract_tdata_key(["596696702021", "tdata"]) == "596696702021"
    assert _extract_tdata_key(["Batch1", "596696702021"]) == "596696702021"
    assert _extract_tdata_key(["my_tdata"]) == "my_tdata"
    assert _extract_tdata_key([]) is None


# ── 3. Case Insensitivity ─────────────────────────────────────────────────────

def test_case_insensitive_matching():
    zip1 = _create_zip_bytes({
        "596696702021.SESSION": b"session_data_upper",
        "Config.Json": b'{"key": "val1"}',
        "596696702021/D877F783": b"tdata_data_upper",
    })
    zip2 = _create_zip_bytes({
        "596696702021.session": b"session_data_lower",
        "config.json": b'{"key": "val2"}',
        "596696702021/D877F783": b"tdata_data_lower",
    })

    res = compare_archives(zip1, zip2)
    assert res.tdata_count == 1
    assert res.session_count == 1
    assert res.json_count == 1
    assert res.total == 3
    assert res.output_bytes is not None

    with zipfile.ZipFile(io.BytesIO(res.output_bytes)) as zf:
        names = zf.namelist()
        assert "596696702021.SESSION" in names
        assert "Config.Json" in names
        assert "596696702021/D877F783" in names
        assert zf.read("596696702021.SESSION") == b"session_data_upper"


# ── 4. Implicit Tdata Folders (No Directory Headers) ──────────────────────────

def test_implicit_tdata_folders():
    # Neither ZIP contains explicit directory headers ending with '/'
    zip1 = _create_zip_bytes({
        "596696702021/D877F783": b"file1",
        "596696702021/map0": b"file2",
    })
    zip2 = _create_zip_bytes({
        "596696702021/D877F783": b"file1_other",
    })

    res = compare_archives(zip1, zip2)
    assert res.tdata_count == 1
    assert res.total == 1
    assert res.output_bytes is not None

    with zipfile.ZipFile(io.BytesIO(res.output_bytes)) as zf:
        assert "596696702021/D877F783" in zf.namelist()
        assert "596696702021/map0" in zf.namelist()


# ── 5. Empty & No Match Handling ──────────────────────────────────────────────

def test_empty_and_no_match():
    zip1 = _create_zip_bytes({"account1.session": b"a1"})
    zip2 = _create_zip_bytes({"account2.session": b"a2"})

    res = compare_archives(zip1, zip2)
    assert res.total == 0
    assert res.output_bytes is None
    assert res.tdata_count == 0
    assert res.session_count == 0
    assert res.json_count == 0


# ── 6. Corrupted ZIP Handling ─────────────────────────────────────────────────

def test_corrupted_zip_raises_value_error():
    valid_zip = _create_zip_bytes({"test.session": b"data"})
    corrupted_bytes = b"this is not a zip archive"

    with pytest.raises(ValueError, match="Corrupted or invalid ZIP archive"):
        compare_archives(corrupted_bytes, valid_zip)

    with pytest.raises(ValueError, match="Corrupted or invalid ZIP archive"):
        compare_archives(valid_zip, corrupted_bytes)


# ── 7. Full Integration Test (Real Files on Disk) ──────────────────────────────

def test_full_integration_real_archives_on_disk(tmp_path: Path):
    path1 = tmp_path / "archive1.zip"
    path2 = tmp_path / "archive2.zip"

    # Build real archive 1 with sessions, json, tdata, and nested files
    files1 = {
        "common_acc.session": b"session_content_1",
        "unique_1.session": b"unique_content_1",
        "metadata.json": b'{"app": "bot"}',
        "596696702021/D877F783": b"tdata_secret_key",
        "596696702021/map0": b"tdata_map_0",
        "Batch/888999/D877F783": b"nested_tdata",
    }
    with zipfile.ZipFile(path1, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, c in files1.items():
            zf.writestr(p, c)

    # Build real archive 2 with matching common items plus extra items
    files2 = {
        "common_acc.session": b"session_content_2",
        "unique_2.session": b"unique_content_2",
        "metadata.json": b'{"app": "bot_v2"}',
        "596696702021/D877F783": b"tdata_secret_key_2",
        "888999/D877F783": b"nested_tdata_2",
    }
    with zipfile.ZipFile(path2, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, c in files2.items():
            zf.writestr(p, c)

    # Execute service comparing the two disk files
    result = compare_archive_files(path1, path2)

    assert result.session_count == 1   # common_acc
    assert result.json_count == 1      # metadata
    assert result.tdata_count == 2     # 596696702021 and 888999
    assert result.total == 4
    assert result.output_bytes is not None

    # Inspect the generated output ZIP structure & contents
    with zipfile.ZipFile(io.BytesIO(result.output_bytes)) as out_zf:
        names = out_zf.namelist()
        assert "common_acc.session" in names
        assert "metadata.json" in names
        assert "596696702021/D877F783" in names
        assert "596696702021/map0" in names
        assert "Batch/888999/D877F783" in names

        # Verify content matches Archive 1 exactly
        assert out_zf.read("common_acc.session") == b"session_content_1"
        assert out_zf.read("metadata.json") == b'{"app": "bot"}'
        assert out_zf.read("596696702021/D877F783") == b"tdata_secret_key"
        assert out_zf.read("Batch/888999/D877F783") == b"nested_tdata"

        # Unique 1/2 should NOT be in matched result
        assert "unique_1.session" not in names
        assert "unique_2.session" not in names
