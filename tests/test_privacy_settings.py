"""tests/test_privacy_settings.py — Unit and integration tests for Privacy Settings service."""

import io
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from telethon.errors import (  # type: ignore[import-untyped]
    AuthKeyUnregisteredError,
    PasswordHashInvalidError,
    PrivacyKeyInvalidError,
)

from app.services.privacy_settings import (
    PRESETS,
    RULE_KEY_CLASSES,
    RULE_VALUE_FACTORY,
    PrivacySettingsResult,
    apply_session_privacy,
    process_privacy_settings,
    process_single_session_privacy,
)


def _create_fake_zip(session_names: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in session_names:
            zf.writestr(name, b"fake sqlite database content")
    return buf.getvalue()


# ── 1. Configuration & Presets Integrity ──────────────────────────────────────

def test_preset_definitions():
    assert "maximum" in PRESETS
    assert "medium" in PRESETS
    assert "open" in PRESETS

    max_p = PRESETS["maximum"]
    assert max_p["last_seen"] == "nobody"
    assert max_p["phone_number"] == "nobody"
    assert max_p["profile_photo"] == "contacts"
    assert max_p["group_invites"] == "contacts"


def test_rule_key_classes_and_values():
    assert len(RULE_KEY_CLASSES) == 8
    assert "last_seen" in RULE_KEY_CLASSES
    assert "voice_messages" in RULE_KEY_CLASSES

    for choice in ("everybody", "contacts", "nobody"):
        val_list = RULE_VALUE_FACTORY[choice]()
        assert len(val_list) == 1


def test_locales_privacy_settings_all_languages():
    from app.locales import PRIVACY_SETTINGS_MESSAGES

    supported_langs = {"en", "bn", "hi", "ur", "ar", "zh"}
    assert set(PRIVACY_SETTINGS_MESSAGES.keys()) == supported_langs

    required_keys = {
        "prompt_file",
        "prompt_2fa",
        "prompt_mode",
        "prompt_preset",
        "prompt_rule_key",
        "prompt_rule_value",
        "processing",
        "done",
        "btn_preset",
        "btn_custom",
        "btn_apply_custom",
        "btn_total",
        "btn_ok",
        "btn_failed",
        "invalid_file",
        "presets",
        "rules",
        "values",
    }

    for lang in supported_langs:
        lang_dict = PRIVACY_SETTINGS_MESSAGES[lang]
        missing = required_keys - set(lang_dict.keys())
        assert not missing, f"Language '{lang}' missing keys: {missing}"
        assert len(lang_dict["rules"]) == 8
        assert len(lang_dict["values"]) == 3
        assert len(lang_dict["presets"]) == 4



# ── 2. apply_session_privacy Execution ────────────────────────────────────────

@pytest.mark.asyncio
async def test_apply_session_privacy_success():
    client = AsyncMock()
    rules = {
        "last_seen": "nobody",
        "phone_number": "nobody",
        "profile_photo": "contacts",
    }
    res = await apply_session_privacy(client, rules, verify=False)
    assert client.call_count == 3
    assert len(res) == 3
    assert all(r.status == "applied" for r in res.values())


@pytest.mark.asyncio
async def test_apply_session_privacy_handles_privacy_key_invalid():
    client = AsyncMock()
    client.side_effect = PrivacyKeyInvalidError(request=None)
    rules = {"voice_messages": "nobody"}

    # Should not raise exception
    await apply_session_privacy(client, rules)
    assert client.call_count == 1


# ── 3. Single Session Processing ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_single_session_success(tmp_path: Path):
    session_file = tmp_path / "test.session"
    session_file.write_bytes(b"sqldb")

    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    with patch("app.services.privacy_settings.TelegramClient", return_value=mock_client):
        detail = await process_single_session_privacy(
            session_file=session_file,
            password=None,
            rules={"last_seen": "nobody"},
            api_id=12345,
            api_hash="hash",
        )

    assert detail.status == "ok"
    assert detail.session_name == "test.session"
    assert detail.error is None


@pytest.mark.asyncio
async def test_single_session_unauthorized(tmp_path: Path):
    session_file = tmp_path / "unauth.session"
    session_file.write_bytes(b"sqldb")

    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = False

    with patch("app.services.privacy_settings.TelegramClient", return_value=mock_client):
        detail = await process_single_session_privacy(
            session_file=session_file,
            password=None,
            rules={"last_seen": "nobody"},
            api_id=12345,
            api_hash="hash",
        )

    assert detail.status == "unauthorized"
    assert "Unauthorized" in str(detail.error)


@pytest.mark.asyncio
async def test_single_session_invalid_2fa_password(tmp_path: Path):
    session_file = tmp_path / "protected.session"
    session_file.write_bytes(b"sqldb")

    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = False
    mock_client.sign_in.side_effect = PasswordHashInvalidError(request=None)

    with patch("app.services.privacy_settings.TelegramClient", return_value=mock_client):
        detail = await process_single_session_privacy(
            session_file=session_file,
            password="wrong_password",
            rules={"last_seen": "nobody"},
            api_id=12345,
            api_hash="hash",
        )

    assert detail.status == "unauthorized"
    assert "Invalid 2FA Password" in str(detail.error)


@pytest.mark.asyncio
async def test_single_session_deactivated(tmp_path: Path):
    session_file = tmp_path / "dead.session"
    session_file.write_bytes(b"sqldb")

    mock_client = AsyncMock()
    mock_client.connect.side_effect = AuthKeyUnregisteredError(request=None)

    with patch("app.services.privacy_settings.TelegramClient", return_value=mock_client):
        detail = await process_single_session_privacy(
            session_file=session_file,
            password=None,
            rules={"last_seen": "nobody"},
            api_id=12345,
            api_hash="hash",
        )

    assert detail.status == "unauthorized"
    assert "Session expired" in str(detail.error)


# ── 4. Batch & Archive Processing (process_privacy_settings) ────────────────

@pytest.mark.asyncio
async def test_process_privacy_settings_zip_archive(tmp_path: Path):
    zip_path = tmp_path / "sessions.zip"
    zip_bytes = _create_fake_zip(["acc1.session", "acc2.session"])
    zip_path.write_bytes(zip_bytes)

    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    with patch("app.services.privacy_settings.TelegramClient", return_value=mock_client):
        res: PrivacySettingsResult = await process_privacy_settings(
            input_path=zip_path,
            password=None,
            preset_name="maximum",
        )

    assert res.total == 2
    assert res.succeeded == 2
    assert res.failed == 0
    assert res.preset_name == "maximum"
    assert len(res.details) == 2


@pytest.mark.asyncio
async def test_process_privacy_settings_empty_archive(tmp_path: Path):
    zip_path = tmp_path / "empty.zip"
    zip_bytes = _create_fake_zip([])
    zip_path.write_bytes(zip_bytes)

    res = await process_privacy_settings(
        input_path=zip_path,
        preset_name="medium",
    )

    assert res.total == 0
    assert res.succeeded == 0
    assert res.failed == 0
    assert res.details == []
