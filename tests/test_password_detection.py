"""tests/test_password_detection.py — Tests for 2FA password auto-detection."""

import zipfile
from pathlib import Path


def _build_zip(zip_path: Path, files: dict[str, object]) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            if isinstance(content, bytes):
                zf.writestr(name, content)
            else:
                zf.writestr(name, content)


def test_json_twofa_field_detected(tmp_path: Path) -> None:
    from app.services.password_detection import detect_zip_passwords

    zip_path = tmp_path / "accounts.zip"
    _build_zip(
        zip_path,
        {
            "acc1.session": b"",
            "acc1.json": '{"api_id": 123, "twofa": "alpha222"}',
            "acc2.session": b"",
            "acc2.json": '{"session": {"password": "beta333"}}',
        },
    )
    per_session, default = detect_zip_passwords(zip_path)

    assert per_session["acc1.session"] == "alpha222"
    assert per_session["acc2.session"] == "beta333"
    assert default is None


def test_password_key_case_insensitive(tmp_path: Path) -> None:
    from app.services.password_detection import detect_zip_passwords

    zip_path = tmp_path / "accounts.zip"
    _build_zip(
        zip_path,
        {
            "x.session": b"",
            "x.json": '{"TwoFA": "CaseP@ss1"}',
        },
    )
    per_session, _ = detect_zip_passwords(zip_path)
    assert per_session["x.session"] == "CaseP@ss1"


def test_folder_txt_sidecar(tmp_path: Path) -> None:
    from app.services.password_detection import detect_zip_passwords

    zip_path = tmp_path / "accounts.zip"
    _build_zip(
        zip_path,
        {
            "acc1/session.session": b"",
            "acc1/2FA.txt": "P@ss2341\n",
            "acc2/session.session": b"",
            "acc2/twoFA.TXT": "P@ss8989\n",
            "note.txt": "all good",
        },
    )
    per_session, default = detect_zip_passwords(zip_path)

    assert per_session["acc1/session.session"] == "P@ss2341"
    assert per_session["acc2/session.session"] == "P@ss8989"
    assert default is None


def test_root_default_password_applies_to_all(tmp_path: Path) -> None:
    from app.services.password_detection import detect_zip_passwords

    zip_path = tmp_path / "accounts.zip"
    _build_zip(
        zip_path,
        {
            "a.session": b"",
            "b.session": b"",
            "password.txt": "GlobalP@ss1\n",
        },
    )
    per_session, default = detect_zip_passwords(zip_path)

    assert per_session == {}
    assert default == "GlobalP@ss1"


def test_zip_without_sessions_returns_empty(tmp_path: Path) -> None:
    from app.services.password_detection import detect_zip_passwords

    zip_path = tmp_path / "empty.zip"
    _build_zip(zip_path, {"readme.txt": "hello"})
    per_session, default = detect_zip_passwords(zip_path)

    assert per_session == {}
    assert default is None


def test_adjacent_json_sidecar(tmp_path: Path) -> None:
    from app.services.password_detection import detect_adjacent_passwords

    session_file = tmp_path / "acc.session"
    session_file.write_bytes(b"")
    (tmp_path / "acc.json").write_text('{"2fa": "NearP@ss9"}')

    per_session, default = detect_adjacent_passwords(session_file)

    assert per_session["acc.session"] == "NearP@ss9"
    assert default is None


def test_adjacent_txt_sidecar(tmp_path: Path) -> None:
    from app.services.password_detection import detect_adjacent_passwords

    session_file = tmp_path / "acc.session"
    session_file.write_bytes(b"")
    (tmp_path / "2fa.txt").write_text("Near2faP@ss\n")

    per_session, _ = detect_adjacent_passwords(session_file)

    assert per_session["acc.session"] == "Near2faP@ss"


def test_json_value_number_detected(tmp_path: Path) -> None:
    from app.services.password_detection import detect_zip_passwords

    zip_path = tmp_path / "accounts.zip"
    _build_zip(
        zip_path,
        {
            "num.session": b"",
            "num.json": '{"password": 123456}',
        },
    )
    per_session, _ = detect_zip_passwords(zip_path)
    assert per_session["num.session"] == "123456"
