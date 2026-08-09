from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.profile_automation import (
    MIN_USERNAME_LEN,
    USERNAME_RE,
    auto_apply_account_profile,
    country_locale,
    country_nat,
    download_profile_photo,
    generate_profile_draft,
    make_unique_username,
)


def test_country_locale_known_regions():
    assert country_locale("+14155552671") == "en_US"
    assert country_locale("+442071838750") == "en_GB"
    assert country_locale("+74951234567") == "ru_RU"
    assert country_locale("+989123456789") == "fa_IR"
    assert country_locale("+8801712345678") == "bn_BD"
    assert country_locale("+5511999999999") == "pt_BR"


def test_country_locale_fallback():
    assert country_locale("+15551234567") == "en_US"
    assert country_locale("garbage") == "en_US"
    assert country_locale("") == "en_US"


def test_country_nat_known_and_fallback():
    assert country_nat("+14155552671") == "US"
    assert country_nat("+5511999999999") == "BR"
    assert country_nat("+881234567890") == "US"


def test_make_unique_username_shape():
    used: set[str] = set()
    username = make_unique_username("John", "Smith", used)
    assert USERNAME_RE.match(username)
    assert MIN_USERNAME_LEN <= len(username) <= 32
    assert not username[0].isdigit()
    assert username in used


def test_make_unique_username_batch_unique():
    used: set[str] = set()
    first = make_unique_username("John", "Smith", used)
    second = make_unique_username("John", "Smith", used)
    assert first != second
    assert len({first, second}) == 2


def test_make_unique_username_short_names():
    used: set[str] = set()
    username = make_unique_username("A", "B", used)
    assert MIN_USERNAME_LEN <= len(username) <= 32
    assert not username[0].isdigit()


def test_generate_profile_draft_real_faker():
    used: set[str] = set()
    draft = generate_profile_draft("+14155552671", used)
    assert draft.first_name
    assert draft.last_name
    assert draft.about
    assert draft.gender in {"male", "female"}
    assert draft.region == "US"
    assert draft.username in used

    second = generate_profile_draft("+14155552671", used)
    assert second.username != draft.username


def test_generate_profile_draft_country_matched():
    used: set[str] = set()
    draft = generate_profile_draft("+989123456789", used)
    assert draft.locale == "fa_IR"
    assert draft.region == "IR"


@pytest.mark.asyncio
async def test_download_profile_photo_success():
    import aiohttp

    class MockPhotoResp:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def read(self):
            return b"\xff\xd8\xff" + b"\x00" * 2048

    class MockApiResp:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def json(self):
            return {"results": [{"picture": {"large": "https://x/p.jpg"}}]}

    def fake_get(url, **kwargs):
        if "api" in url:
            return MockApiResp()
        return MockPhotoResp()

    class MockSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def get(self, url, **kwargs):
            return fake_get(url, **kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(aiohttp, "ClientSession", MockSession)
        photo = await download_profile_photo("female", "US")
    assert photo is not None
    assert photo.startswith(b"\xff\xd8\xff")


@pytest.mark.asyncio
async def test_download_profile_photo_rejects_garbage():
    import aiohttp

    class MockApiResp:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def json(self):
            return {"results": [{"picture": {"large": "https://x/p.jpg"}}]}

    class MockPhotoResp:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def read(self):
            return b"not an image"

    def fake_get(url, **kwargs):
        if "api" in url:
            return MockApiResp()
        return MockPhotoResp()

    class MockSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def get(self, url, **kwargs):
            return fake_get(url, **kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(aiohttp, "ClientSession", MockSession)
        photo = await download_profile_photo("male", "US")
    assert photo is None


@pytest.mark.asyncio
async def test_download_profile_photo_http_error():
    import aiohttp

    class MockApiResp:
        status = 500

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class MockSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def get(self, url, **kwargs):
            return MockApiResp()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(aiohttp, "ClientSession", MockSession)
        photo = await download_profile_photo("female", "US")
    assert photo is None


@pytest.mark.asyncio
async def test_auto_apply_account_profile_writes_and_cleans_photo(tmp_path: Path):
    class DummyDraft:
        first_name = "John"
        last_name = "Smith"
        username = "johnsmith"
        about = "Engineer"
        gender = "male"
        locale = "en_US"

    session_file = tmp_path / "acc.session"
    session_file.write_bytes(b"session-data")
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()

    with patch(
        "app.services.profile_automation.update_account_profile",
        return_value=True,
    ) as mock_update:
        ok = await auto_apply_account_profile(
            session_file,
            [(123, "hash")],
            DummyDraft(),
            b"\xff\xd8\xff" + b"\x00" * 2048,
            photo_dir,
        )

    assert ok is True
    mock_update.assert_called_once()
    assert list(photo_dir.iterdir()) == []

