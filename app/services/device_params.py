"""device_params.py — Service for parsing authentic device parameters from device_params.zip.

Provides realistic Telegram Desktop device fingerprints for Telethon client connections
to improve session quality and prevent immediate anti-spam restrictions (limiting).
"""
from __future__ import annotations

import hashlib
import logging
import random
import sqlite3
import zipfile
from pathlib import Path

LOGGER = logging.getLogger(__name__)

# Default fallbacks if device_params.zip is absent or unreadable
_DEFAULT_DEVICE_MODELS = [
    "PC 64bit:Windows 10",
    "PC 64bit:Windows 11",
    "Desktop:Windows 10",
    "Desktop:Windows 11",
    "Workstation:Windows 10",
    "Workstation:Windows 11",
]

_DEFAULT_SYSTEM_VERSIONS = [
    "Windows 10 Pro 19045",
    "Windows 10 Home 19045",
    "Windows 11 Pro 22621",
    "Windows 11 Pro 22631",
    "Windows 11 Home 22631",
]

_DEFAULT_APP_VERSIONS = [
    "4.12.2 x64",
    "4.11.6 x64",
    "4.10.3 x64",
    "4.9.3 x64",
    "4.8.4 x64",
]

_LANG_PAIR_MAP = {
    "en": "en-US",
    "ru": "ru-RU",
    "es": "es-ES",
    "de": "de-DE",
    "fr": "fr-FR",
    "fa": "fa-IR",
    "ar": "ar-SA",
    "tr": "tr-TR",
    "zh": "zh-CN",
    "zh-hans": "zh-CN",
}

_DEFAULT_LANG_CODES = list(_LANG_PAIR_MAP.keys())
_CACHED_PARAMS: dict[str, list[str]] | None = None
_STABLE_CACHE: dict[str, dict[str, str]] = {}


def _extract_seed_from_file(path: Path) -> str | None:
    """Attempt to extract the auth_key or internal session seed from a SQLite .session file.

    If the file exists and contains a valid Telethon/Pyrogram auth_key, returning its SHA256 hex
    guarantees that even if the session file is copied or extracted into temporary directories with
    random path names, get_stable_device_params will ALWAYS return the exact same fingerprint.
    """
    target_path = path if path.is_file() else path.with_suffix(".session")
    if not target_path.is_file() or target_path.stat().st_size == 0:
        return None

    try:
        with sqlite3.connect(f"file:{target_path}?mode=ro", uri=True) as conn:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            if "sessions" in tables:
                row = conn.execute("SELECT auth_key FROM sessions LIMIT 1").fetchone()
                if row and row[0]:
                    auth_key = bytes(row[0])
                    if len(auth_key) == 256 and any(auth_key):
                        return f"authkey:{hashlib.sha256(auth_key).hexdigest()}"
    except (sqlite3.Error, OSError, ValueError) as exc:
        LOGGER.debug("Could not read auth_key from sqlite %s: %s", path, exc)

    return None


def _load_zip_params(zip_path: Path) -> dict[str, list[str]]:
    """Parse text lists from device_params.zip."""
    params: dict[str, list[str]] = {}
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            for member in archive.namelist():
                if not member.endswith(".txt"):
                    continue
                name = Path(member).stem
                lines = [
                    line.strip()
                    for line in archive.read(member).decode("utf-8", errors="ignore").splitlines()
                    if line.strip()
                ]
                if lines:
                    params[name] = lines
    except (zipfile.BadZipFile, OSError, KeyError) as exc:
        LOGGER.warning("Could not parse device_params.zip at %s: %s", zip_path, exc)
    return params


def get_device_params_store() -> dict[str, list[str]]:
    """Return cached or loaded device parameter dictionary."""
    global _CACHED_PARAMS
    if _CACHED_PARAMS is not None:
        return _CACHED_PARAMS

    project_root = Path(__file__).resolve().parent.parent.parent
    possible_paths = [
        project_root / "device_params.zip",
        Path.cwd() / "device_params.zip",
    ]

    loaded: dict[str, list[str]] = {}
    for p in possible_paths:
        if p.is_file():
            loaded = _load_zip_params(p)
            if loaded:
                LOGGER.info("Loaded authentic device parameters from %s (%d parameter sets)", p, len(loaded))
                break

    _CACHED_PARAMS = loaded
    return _CACHED_PARAMS


def _match_system_lang(lang_code: str, available_system_langs: list[str]) -> str:
    """Pair a system_lang_code with a given lang_code."""
    if lang_code in _LANG_PAIR_MAP:
        mapped = _LANG_PAIR_MAP[lang_code]
        if mapped in available_system_langs or not available_system_langs:
            return mapped
    prefix = lang_code.split("-")[0].lower()
    for sys_lang in available_system_langs:
        if sys_lang.lower().startswith(prefix):
            return sys_lang
    return available_system_langs[0] if available_system_langs else "en-US"


def get_random_device_params() -> dict[str, str]:
    """Return a randomised dictionary of Telethon device parameters."""
    store = get_device_params_store()

    device_models = store.get("device_model") or _DEFAULT_DEVICE_MODELS
    system_versions = store.get("system_version") or _DEFAULT_SYSTEM_VERSIONS
    app_versions = store.get("app_version") or _DEFAULT_APP_VERSIONS
    lang_codes = store.get("lang_code") or _DEFAULT_LANG_CODES
    system_lang_codes = store.get("system_lang_code") or list(_LANG_PAIR_MAP.values())

    lang_code = random.choice(lang_codes)
    system_lang_code = _match_system_lang(lang_code, system_lang_codes)

    return {
        "device_model": random.choice(device_models),
        "system_version": random.choice(system_versions),
        "app_version": random.choice(app_versions),
        "lang_code": lang_code,
        "system_lang_code": system_lang_code,
    }


def get_stable_device_params(seed: str | Path) -> dict[str, str]:
    """Return a deterministic, stable set of Telethon device parameters for a given seed.

    If seed points to an existing SQLite .session file, the fingerprint is derived directly from its
    auth_key to remain 100% invariant across temporary directory extractions. Otherwise, it falls
    back to hashing the seed string or file basename.
    """
    path_obj: Path | None = None
    if isinstance(seed, Path):
        path_obj = seed
    elif isinstance(seed, str) and (seed.endswith(".session") or "/" in seed or "\\" in seed):
        path_obj = Path(seed)

    content_seed: str | None = None
    if path_obj is not None:
        content_seed = _extract_seed_from_file(path_obj)

    if content_seed is not None:
        seed_key = content_seed
    elif path_obj is not None:
        seed_key = path_obj.name
    else:
        seed_key = str(seed)

    if seed_key in _STABLE_CACHE:
        return _STABLE_CACHE[seed_key]

    digest = hashlib.sha256(seed_key.encode("utf-8")).digest()
    num = int.from_bytes(digest[:8], byteorder="big")

    store = get_device_params_store()

    device_models = store.get("device_model") or _DEFAULT_DEVICE_MODELS
    system_versions = store.get("system_version") or _DEFAULT_SYSTEM_VERSIONS
    app_versions = store.get("app_version") or _DEFAULT_APP_VERSIONS
    lang_codes = store.get("lang_code") or _DEFAULT_LANG_CODES
    system_lang_codes = store.get("system_lang_code") or list(_LANG_PAIR_MAP.values())

    device_model = device_models[num % len(device_models)]
    system_version = system_versions[(num >> 8) % len(system_versions)]
    app_version = app_versions[(num >> 16) % len(app_versions)]
    lang_code = lang_codes[(num >> 24) % len(lang_codes)]
    system_lang_code = _match_system_lang(lang_code, system_lang_codes)

    params = {
        "device_model": device_model,
        "system_version": system_version,
        "app_version": app_version,
        "lang_code": lang_code,
        "system_lang_code": system_lang_code,
    }

    _STABLE_CACHE[seed_key] = params
    return params
