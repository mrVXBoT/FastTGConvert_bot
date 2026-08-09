"""app/services/proxy.py — Production-grade Fernet-encrypted per-user proxy resolver and multi-DC health checker."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import os
import urllib.parse

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session, sessionmaker

from app.db.repositories import get_user_proxy

LOGGER = logging.getLogger(__name__)

# List of official Telegram Data Center (DC) endpoints for proxy connectivity tests
TELEGRAM_DC_ENDPOINTS: list[tuple[str, int]] = [
    ("149.154.175.50", 443),   # DC1
    ("149.154.167.51", 443),   # DC2
    ("149.154.175.100", 443),  # DC3
    ("149.154.167.91", 443),   # DC4
    ("91.108.56.130", 443),    # DC5
]


def _get_fernet() -> Fernet:
    """Retrieve Fernet instance initialized strictly from PROXY_ENCRYPTION_KEY environment or settings configuration.

    Raises RuntimeError if PROXY_ENCRYPTION_KEY is missing (Fail Fast).
    """
    raw_key = os.getenv("PROXY_ENCRYPTION_KEY", "").strip()
    if not raw_key:
        try:
            from app.config import get_settings

            raw_key = get_settings().proxy_encryption_key.strip()
        except Exception:  # noqa: BLE001
            raw_key = ""

    if not raw_key:
        raise RuntimeError(
            "Missing PROXY_ENCRYPTION_KEY environment variable. "
            "A secret key is required for production proxy password encryption."
        )

    try:
        return Fernet(raw_key.encode("utf-8"))
    except Exception:  # noqa: BLE001
        derived_32bytes = base64.urlsafe_b64encode(
            hashlib.sha256(raw_key.encode("utf-8")).digest()
        )
        return Fernet(derived_32bytes)


def encrypt_proxy_password(password: str | None) -> str | None:
    """Encrypt a plaintext proxy password using Fernet symmetric encryption."""
    if not password or not password.strip():
        return None
    try:
        fernet = _get_fernet()
        return fernet.encrypt(password.encode("utf-8")).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Failed to encrypt proxy password: %s", exc)
        return None


def decrypt_proxy_password(encrypted_password: str | None) -> str | None:
    """Decrypt a Fernet-encrypted proxy password back to plaintext.

    Returns None if decryption fails or token is invalid.
    NEVER returns the encrypted ciphertext string.
    """
    if not encrypted_password:
        return None
    try:
        fernet = _get_fernet()
        return fernet.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        LOGGER.warning("Invalid token when decrypting proxy password; returning None")
        return None
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Failed to decrypt proxy password: %s", exc)
        return None


def parse_telethon_proxy(
    proxy_str: str | None,
) -> tuple[str, str, int, bool, str | None, str | None] | None:
    """Parse a proxy URL string (e.g. 'socks5://user:pass@host:port') into a Telethon proxy tuple.

    Tuple format expected by Telethon with python-socks:
      (proxy_type, addr, port, rdns, username, password)
    where proxy_type is 'socks5', 'socks4', or 'http'.
    """
    if not proxy_str:
        return None
    try:
        parsed = urllib.parse.urlparse(proxy_str)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("socks5", "socks4", "http", "https"):
            return None
        proxy_type = "http" if scheme in ("http", "https") else scheme
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            return None
        username = parsed.username
        password = parsed.password
        return (proxy_type, host, port, True, username, password)
    except (ValueError, TypeError, AttributeError):
        return None


def resolve_user_proxy(
    session_factory: sessionmaker[Session] | None,
    user_id: int | None,
    default_proxy: str | None = None,
) -> tuple[str, str, int, bool, str | None, str | None] | None:
    """Resolve the per-user proxy tuple from DB for the specified user_id.

    Decrypts the stored password and returns the resolved proxy tuple.
    Falls back to default_proxy if user has no custom proxy set.
    """
    proxy_str: str | None = None
    if session_factory is not None and user_id is not None:
        try:
            with session_factory() as session:
                proxy_str = get_user_proxy(session, user_id)
        except Exception:  # noqa: BLE001
            proxy_str = None

    if not proxy_str and default_proxy:
        proxy_str = default_proxy

    parsed = parse_telethon_proxy(proxy_str)
    if not parsed:
        return None

    proxy_type, host, port, rdns, username, enc_password = parsed
    decrypted_password = decrypt_proxy_password(enc_password)
    return (proxy_type, host, port, rdns, username, decrypted_password)


async def _run_multi_dc_check(
    proxy: object, per_endpoint_timeout: float = 3.0
) -> tuple[bool, str]:
    """Test connection across Telegram DC endpoints with dedicated per-endpoint timeout.

    Endpoints are probed in parallel and the first success wins, so a slow
    (but alive) DC never delays the verdict.
    """

    async def try_endpoint(dc_host: str, dc_port: int) -> tuple[bool, str]:
        try:
            sock = await asyncio.wait_for(
                proxy.connect(dest_host=dc_host, dest_port=dc_port),  # type: ignore[attr-defined]
                timeout=per_endpoint_timeout,
            )
            sock.close()
            return True, f"Proxy connection successful (connected to Telegram DC {dc_host})"
        except Exception:  # noqa: BLE001
            return False, f"Failed to connect to Telegram DC {dc_host}"

    outcomes = await asyncio.gather(
        *(try_endpoint(dc_host, dc_port) for dc_host, dc_port in TELEGRAM_DC_ENDPOINTS)
    )
    for ok, detail in outcomes:
        if ok:
            return True, detail
    return False, "Failed to connect to any Telegram DC endpoint through proxy"


async def test_proxy_connection(
    proxy_tuple: tuple[str, str, int, bool, str | None, str | None] | None,
    timeout: float = 10.0,
) -> tuple[bool, str]:
    """Perform a live TCP handshake test across Telegram's official DC endpoints (max 10s total).

    Returns (is_successful, detail_message).
    """
    if not proxy_tuple:
        return True, "No proxy specified"

    proxy_type, host, port, _rdns, username, password = proxy_tuple
    try:
        from python_socks import ProxyType  # type: ignore[import-untyped]
        from python_socks.async_.asyncio import Proxy  # type: ignore[import-untyped]

        ptype = (
            ProxyType.SOCKS5
            if proxy_type == "socks5"
            else (ProxyType.SOCKS4 if proxy_type == "socks4" else ProxyType.HTTP)
        )
        proxy = Proxy(
            proxy_type=ptype,
            host=host,
            port=port,
            username=username,
            password=password,
        )

        from app.core import METRICS

        res_ok, detail = await asyncio.wait_for(
            _run_multi_dc_check(proxy, per_endpoint_timeout=3.0),
            timeout=timeout,
        )
        if res_ok:
            METRICS.inc_counter("proxy_success_total")
        else:
            METRICS.inc_counter("proxy_failure_total", labels={"reason": "unreachable"})
        return res_ok, detail
    except TimeoutError:
        from app.core import METRICS

        METRICS.inc_counter("proxy_failure_total", labels={"reason": "timeout"})
        return False, f"Proxy connection check timed out overall ({timeout}s)"
    except Exception as exc:  # noqa: BLE001
        from app.core import METRICS

        METRICS.inc_counter("proxy_failure_total", labels={"reason": "exception"})
        LOGGER.debug("Proxy connection test error: %s", exc)
        return False, f"Proxy connection error: {exc}"
