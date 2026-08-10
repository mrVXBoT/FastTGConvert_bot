"""tests/test_proxy.py — Unit tests for proxy parsing and per-user resolution."""

from unittest.mock import MagicMock, patch

from app.services.proxy import parse_telethon_proxy, resolve_user_proxy


def test_parse_telethon_socks5_with_credentials() -> None:
    res = parse_telethon_proxy("socks5://user:pass@127.0.0.1:1080")
    assert res == ("socks5", "127.0.0.1", 1080, True, "user", "pass")


def test_parse_telethon_socks5_without_credentials() -> None:
    res = parse_telethon_proxy("socks5://192.168.1.1:8080")
    assert res == ("socks5", "192.168.1.1", 8080, True, None, None)


def test_parse_telethon_http_proxy() -> None:
    res = parse_telethon_proxy("http://admin:secret@proxy.com:3128")
    assert res == ("http", "proxy.com", 3128, True, "admin", "secret")


def test_parse_telethon_invalid_proxy_urls() -> None:
    assert parse_telethon_proxy(None) is None
    assert parse_telethon_proxy("") is None
    assert parse_telethon_proxy("ftp://1.2.3.4:1080") is None
    assert parse_telethon_proxy("not_a_url") is None
    assert parse_telethon_proxy("socks5://host_without_port") is None


def test_parse_telethon_telegram_deep_link() -> None:
    res = parse_telethon_proxy(
        "https://t.me/socks?server=d10.xenett.xyz&port=555&user=vx&pass=vx"
    )
    assert res == ("socks5", "d10.xenett.xyz", 555, True, "vx", "vx")

    res_tg = parse_telethon_proxy(
        "tg://socks?server=d10.xenett.xyz&port=555&user=vx&pass=vx"
    )
    assert res_tg == ("socks5", "d10.xenett.xyz", 555, True, "vx", "vx")

    res_partial = parse_telethon_proxy(
        "socks?server=d10.xenett.xyz&port=555&user=vx&pass=vx"
    )
    assert res_partial == ("socks5", "d10.xenett.xyz", 555, True, "vx", "vx")

    res_colon = parse_telethon_proxy("d10.xenett.xyz:555:vx:vx")
    assert res_colon == ("socks5", "d10.xenett.xyz", 555, True, "vx", "vx")




def test_resolve_user_proxy_returns_user_custom_proxy() -> None:
    from app.services.proxy import encrypt_proxy_password

    mock_session = MagicMock()
    mock_sf = MagicMock(return_value=mock_session)
    enc_pass = encrypt_proxy_password("mypass")

    with patch(
        "app.services.proxy.get_user_proxy",
        return_value=f"socks5://myuser:{enc_pass}@1.1.1.1:1080",
    ):
        res = resolve_user_proxy(mock_sf, 12345)

    assert res == ("socks5", "1.1.1.1", 1080, True, "myuser", "mypass")


def test_resolve_user_proxy_falls_back_to_default() -> None:
    mock_session = MagicMock()
    mock_sf = MagicMock(return_value=mock_session)

    with patch("app.services.proxy.get_user_proxy", return_value=None):
        res = resolve_user_proxy(mock_sf, 12345, default_proxy="http://default.proxy:8080")

    assert res == ("http", "default.proxy", 8080, True, None, None)


def test_get_fernet_uses_fallback_when_missing_key() -> None:
    from cryptography.fernet import Fernet

    from app.services.proxy import _get_fernet

    with patch.dict("os.environ", {"PROXY_ENCRYPTION_KEY": ""}, clear=True):
        assert isinstance(_get_fernet(), Fernet)


def test_encrypt_proxy_password_null_safety() -> None:
    from app.services.proxy import encrypt_proxy_password

    assert encrypt_proxy_password(None) is None
    assert encrypt_proxy_password("") is None
    assert encrypt_proxy_password("   ") is None


def test_parse_proxy_pool_multiline() -> None:
    from app.services.proxy import parse_proxy_pool

    raw_text = """
    # Comment line
    socks5://user1:pass1@1.1.1.1:1080
    socks5://user2:pass2@2.2.2.2:1080
    invalid_proxy_format
    https://t.me/socks?server=d10.xenett.xyz&port=555&user=vx&pass=vx
    """
    pool = parse_proxy_pool(raw_text)
    assert len(pool) == 3
    assert pool[0] == "socks5://user1:pass1@1.1.1.1:1080"
    assert pool[1] == "socks5://user2:pass2@2.2.2.2:1080"
    assert pool[2] == "socks5://vx:vx@d10.xenett.xyz:555"


def test_resolve_user_proxy_pool_round_robin() -> None:
    mock_session = MagicMock()
    mock_sf = MagicMock(return_value=mock_session)

    raw_pool = "socks5://user1:pass1@1.1.1.1:1080\nsocks5://user2:pass2@2.2.2.2:1080"

    with patch("app.services.proxy.get_user_proxy", return_value=raw_pool):
        res0 = resolve_user_proxy(mock_sf, 12345, index=0)
        res1 = resolve_user_proxy(mock_sf, 12345, index=1)
        res2 = resolve_user_proxy(mock_sf, 12345, index=2)

    assert res0 == ("socks5", "1.1.1.1", 1080, True, "user1", "pass1")
    assert res1 == ("socks5", "2.2.2.2", 1080, True, "user2", "pass2")
    assert res2 == ("socks5", "1.1.1.1", 1080, True, "user1", "pass1")


def test_resolve_user_proxy_pool_returns_list() -> None:
    from app.services.proxy import resolve_user_proxy_pool

    mock_session = MagicMock()
    mock_sf = MagicMock(return_value=mock_session)

    raw_pool = "socks5://user1:pass1@1.1.1.1:1080\nsocks5://user2:pass2@2.2.2.2:1080"

    with patch("app.services.proxy.get_user_proxy", return_value=raw_pool):
        pool = resolve_user_proxy_pool(mock_sf, 12345)

    assert isinstance(pool, list)
    assert len(pool) == 2
    assert pool[0] == ("socks5", "1.1.1.1", 1080, True, "user1", "pass1")
    assert pool[1] == ("socks5", "2.2.2.2", 1080, True, "user2", "pass2")


