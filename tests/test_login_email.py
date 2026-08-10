import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.login_email import (
    _create_mail_tm_account,
    _poll_mail_tm_otp,
    process_batch_login_email,
    process_single_login_email,
)


class DummyAsyncCM:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        pass


@pytest.mark.asyncio
async def test_create_mail_tm_account():
    mock_session = MagicMock()

    mock_domains_res = MagicMock()
    mock_domains_res.status = 200
    mock_domains_res.json = AsyncMock(return_value={"hydra:member": [{"domain": "test.com"}]})

    mock_acc_res = MagicMock()
    mock_acc_res.status = 201

    mock_token_res = MagicMock()
    mock_token_res.status = 200
    mock_token_res.json = AsyncMock(return_value={"token": "mock_jwt_token"})

    mock_session.get.return_value = DummyAsyncCM(mock_domains_res)
    mock_session.post.side_effect = [
        DummyAsyncCM(mock_acc_res),
        DummyAsyncCM(mock_token_res),
    ]

    res = await _create_mail_tm_account(mock_session)
    assert res is not None
    address, token, base_url = res
    assert address.endswith("@test.com")
    assert token == "mock_jwt_token"
    assert base_url == "https://api.mail.tm"


@pytest.mark.asyncio
async def test_poll_mail_tm_otp():
    mock_session = MagicMock()

    mock_msgs_res = MagicMock()
    mock_msgs_res.status = 200
    mock_msgs_res.json = AsyncMock(return_value={"hydra:member": [{"id": "msg_1"}]})

    mock_detail_res = MagicMock()
    mock_detail_res.status = 200
    mock_detail_res.json = AsyncMock(return_value={"text": "Telegram code is 654321"})

    mock_session.get.side_effect = [
        DummyAsyncCM(mock_msgs_res),
        DummyAsyncCM(mock_detail_res),
    ]

    code = await _poll_mail_tm_otp(mock_session, "token", timeout=5)
    assert code == "654321"


@pytest.mark.asyncio
async def test_process_single_login_email_no_email():
    with tempfile.NamedTemporaryFile(suffix=".session") as tmp:
        session_path = Path(tmp.name)

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.is_user_authorized = AsyncMock(return_value=True)

        me = MagicMock()
        me.phone = "123456789"
        mock_client.get_me = AsyncMock(return_value=me)

        pwd_res = MagicMock()
        pwd_res.login_email_pattern = None
        mock_client.side_effect = [pwd_res]

        with patch("app.services.login_email.TelegramClient", return_value=mock_client):
            res = await process_single_login_email(
                session_path, [(12345, "hash")], AsyncMock()
            )
            assert res.status == "no_email"
            assert res.phone == "123456789"


@pytest.mark.asyncio
async def test_process_batch_login_email_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(zip_path, "w"):
            pass

        res = await process_batch_login_email(
            zip_path, [(123, "hash")], tmp_path / "out"
        )
        assert res.total == 0
        assert res.changed_count == 0
