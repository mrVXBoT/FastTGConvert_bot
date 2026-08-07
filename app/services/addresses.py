"""app/services/addresses.py — Blockchain address validation helpers."""

from __future__ import annotations

import hashlib
import re

_TRON_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _base58_decode(value: str) -> bytes | None:
    n = 0
    for char in value:
        try:
            n = n * 58 + _TRON_BASE58_ALPHABET.index(char)
        except ValueError:
            return None
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    padding = len(value) - len(value.lstrip("1"))
    return b"\x00" * padding + raw


def is_valid_trc20_address(address: str | None) -> bool:
    """True for a valid TRON base58-check encoded address (34 chars, starts with 'T')."""
    value = (address or "").strip()
    if len(value) != 34 or value[0] != "T":
        return False
    if any(char not in _TRON_BASE58_ALPHABET for char in value):
        return False
    payload = _base58_decode(value)
    if payload is None or len(payload) != 25:
        return False
    body, checksum = payload[:-4], payload[-4:]
    return hashlib.sha256(hashlib.sha256(body).digest()).digest()[:4] == checksum


def is_valid_bep20_address(address: str | None) -> bool:
    """True for a valid EVM address (0x + 40 hex)."""
    return bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", (address or "").strip()))


def is_valid_binance_id(value: str | None) -> bool:
    """True for an optional Binance UID: empty/None (not provided) or a 7+ digit ID."""
    digit_value = (value or "").strip()
    if not digit_value:
        return True
    return digit_value.isdigit() and len(digit_value) >= 7