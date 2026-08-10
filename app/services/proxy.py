"""app/services/proxy.py — Production-grade Fernet-encrypted per-user proxy resolver and multi-DC health checker."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import os
import re
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
    """Retrieve Fernet instance initialized from PROXY_ENCRYPTION_KEY environment or settings configuration."""
    raw_key = os.getenv("PROXY_ENCRYPTION_KEY", "").strip()
    if not raw_key:
        try:
            from app.config import get_settings

            raw_key = get_settings().proxy_encryption_key.strip()
        except Exception:  # noqa: BLE001
            raw_key = ""

    if not raw_key:
        raw_key = "DEFAULT_FAST_TG_CONVERT_FALLBACK_KEY_32BYTES_LONG"

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
        LOGGER.debug("Proxy password is unencrypted plaintext or invalid token")
        return None
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Failed to decrypt proxy password: %s", exc)
        return None


def normalize_proxy_string(raw: str | None) -> str | None:
    """Normalize various proxy formats (Telegram t.me/socks links, host:port:user:pass, host:port) into standard URLs."""
    if not raw:
        return None
    raw = raw.strip()

    # 1. Telegram Deep Link (t.me/socks, tg://socks, t.me/proxy, tg://proxy, socks?, proxy?, or server= query string)
    if any(k in raw for k in ("t.me/socks", "tg://socks", "t.me/proxy", "tg://proxy", "socks?", "proxy?")) or ("server=" in raw and "port=" in raw):
        try:
            url_to_parse = raw if ("://" in raw or raw.startswith("t.me/")) else f"https://t.me/{raw.lstrip('/')}"
            parsed = urllib.parse.urlparse(url_to_parse)
            qs = urllib.parse.parse_qs(parsed.query)
            server = (qs.get("server") or qs.get("host") or [""])[0].strip()
            port = (qs.get("port") or [""])[0].strip()
            user = (qs.get("user") or qs.get("username") or [""])[0].strip()
            password = (qs.get("pass") or qs.get("password") or [""])[0].strip()
            if server and port and port.isdigit():
                if user and password:
                    return f"socks5://{user}:{password}@{server}:{port}"
                if user:
                    return f"socks5://{user}@{server}:{port}"
                return f"socks5://{server}:{port}"
        except Exception:  # noqa: BLE001
            pass

    # 2. Add scheme if missing (e.g. host:port:user:pass or host:port)
    if not any(raw.startswith(p) for p in ("socks5://", "socks4://", "http://", "https://", "tg://")):
        parts = raw.split(":")
        if len(parts) == 4 and parts[1].isdigit():
            return f"socks5://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        if len(parts) == 2 and parts[1].isdigit():
            return f"socks5://{parts[0]}:{parts[1]}"
        if not raw.startswith("socks5://"):
            raw = f"socks5://{raw}"

    try:
        parsed = urllib.parse.urlparse(raw)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("socks5", "socks4", "http", "https"):
            return None
        if not parsed.hostname or not parsed.port:
            return None
        if not (1 <= parsed.port <= 65535):
            return None
        return raw
    except Exception:  # noqa: BLE001
        return None


def parse_proxy_pool(text: str | None) -> list[str]:
    """Parse raw text or file content containing multiple proxy lines into a list of unique, normalized SOCKS5/HTTP proxy URLs."""
    if not text:
        return []
    proxies: list[str] = []
    seen: set[str] = set()
    lines = re.split(r"[\r\n,;]+", text)
    for line in lines:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        normalized = normalize_proxy_string(cleaned)
        if normalized and normalized not in seen:
            seen.add(normalized)
            proxies.append(normalized)
    return proxies



def parse_telethon_proxy(
    proxy_str: str | None,
) -> tuple[str, str, int, bool, str | None, str | None] | None:
    """Parse a proxy URL string (e.g. 'socks5://user:pass@host:port' or Telegram link) into a Telethon proxy tuple.

    Tuple format expected by Telethon with python-socks:
      (proxy_type, addr, port, rdns, username, password)
    where proxy_type is 'socks5', 'socks4', or 'http'.
    """
    normalized = normalize_proxy_string(proxy_str)
    if not normalized:
        return None
    try:
        parsed = urllib.parse.urlparse(normalized)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("socks5", "socks4", "http", "https"):
            return None
        proxy_type = "http" if scheme in ("http", "https") else scheme
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            return None
        username = urllib.parse.unquote(parsed.username) if parsed.username else None
        password = urllib.parse.unquote(parsed.password) if parsed.password else None
        return (proxy_type, host, port, True, username, password)
    except (ValueError, TypeError, AttributeError):
        return None


def resolve_user_proxy(
    session_factory: sessionmaker[Session] | None,
    user_id: int | None,
    default_proxy: str | None = None,
    index: int = 0,
) -> tuple[str, str, int, bool, str | None, str | None] | None:
    """Resolve the per-user proxy tuple from DB for the specified user_id.

    Supports Proxy Pools (multi-proxy lists) via Round-Robin index.
    Decrypts the stored password and returns the resolved proxy tuple.
    Falls back to default_proxy if user has no custom proxy set.
    """
    proxy_str: str | None = None
    if session_factory is not None and user_id is not None:
        try:
            with session_factory() as session:
                raw_proxy = get_user_proxy(session, user_id)
                if raw_proxy:
                    lines = [line.strip() for line in raw_proxy.splitlines() if line.strip()]
                    if lines:
                        proxy_str = lines[index % len(lines)]
        except Exception:  # noqa: BLE001
            proxy_str = None

    if not proxy_str and default_proxy:
        proxy_str = default_proxy

    parsed = parse_telethon_proxy(proxy_str)
    if not parsed:
        return None

    proxy_type, host, port, rdns, username, enc_password = parsed
    decrypted_password = decrypt_proxy_password(enc_password) or enc_password
    return (proxy_type, host, port, rdns, username, decrypted_password)


def resolve_user_proxy_pool(
    session_factory: sessionmaker[Session] | None,
    user_id: int | None,
    default_proxy: str | None = None,
) -> tuple[str, str, int, bool, str | None, str | None] | list[tuple[str, str, int, bool, str | None, str | None]] | None:
    """Resolve per-user proxy settings. If user has multiple proxies (Proxy Pool), returns a list of proxy tuples."""
    if session_factory is None or user_id is None:
        return resolve_user_proxy(session_factory, user_id, default_proxy)

    try:
        with session_factory() as session:
            raw_proxy = get_user_proxy(session, user_id)
            if raw_proxy and "\n" in raw_proxy:
                lines = [l.strip() for l in raw_proxy.splitlines() if l.strip()]
                parsed_list = []
                for line in lines:
                    p = parse_telethon_proxy(line)
                    if p:
                        ptype, host, port, rdns, username, enc_password = p
                        dec_password = decrypt_proxy_password(enc_password) or enc_password
                        parsed_list.append((ptype, host, port, rdns, username, dec_password))
                if parsed_list:
                    return parsed_list
    except Exception:  # noqa: BLE001
        pass

    return resolve_user_proxy(session_factory, user_id, default_proxy)




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
