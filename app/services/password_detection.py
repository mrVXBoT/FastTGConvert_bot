"""password_detection.py — Auto-detect 2FA passwords from account sidecars.

Mimics the competitor's "auto-detect" behaviour:

- JSON sidecars: scanned recursively for keys named ``twofa`` / ``password`` /
  ``2fa`` / ``two_factor`` (case-insensitive).
- Text sidecars: any ``.txt`` member whose filename contains ``2fa``,
  ``twofa`` or ``password`` (case-insensitive), e.g. ``2FA.txt``,
  ``twoFA.TXT``, ``password.txt``.

Passwords are paired per session (same stem as the ``.session`` member
first, then the single matching sidecar inside the session's folder).
A single password file at the archive root becomes the default password
for every account without a per-session match.
"""

from __future__ import annotations

import json
import logging
import re
import zipfile
from pathlib import Path

LOGGER = logging.getLogger(__name__)

_PASSWORD_JSON_KEYS = (
    "2fa",
    "twofa",
    "password",
    "two_factor",
    "twofactor",
    "passwd",
    "secret",
)
_PASSWORD_FILENAME_MARKERS = ("2fa", "twofa", "password", "passwd")
_PASSWORD_LINE_RE = re.compile(r"^[0-9A-Za-z!@#$%^&*._\-]{4,200}$")
_MAX_READ_BYTES = 2 * 1024 * 1024


def extract_password_from_json(json_path: Path) -> str | None:
    """Recursively find the first ``twofa``/``password``/``2fa`` value."""
    if not json_path.is_file() or json_path.stat().st_size > _MAX_READ_BYTES:
        return None
    try:
        data = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return None
    return _walk_json_password(data)


def extract_password_from_text(text_path: Path) -> str | None:
    if not text_path.is_file() or text_path.stat().st_size > _MAX_READ_BYTES:
        return None
    try:
        raw = text_path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
    return _extract_text_password(raw)


def _json_value_to_password(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, (dict, list)):
        for item in value.values() if isinstance(value, dict) else value:
            found = _json_value_to_password(item)
            if found:
                return found
    return None


def _walk_json_password(node: object) -> str | None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key.lower().strip() in _PASSWORD_JSON_KEYS:
                found = _json_value_to_password(value)
                if found:
                    return found
        for value in node.values():
            if isinstance(value, (dict, list)):
                found = _walk_json_password(value)
                if found:
                    return found
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, (dict, list)):
                found = _walk_json_password(item)
                if found:
                    return found
    return None


def _extract_text_password(raw: str) -> str | None:
    for line in raw.splitlines():
        line = line.strip().strip("\ufeff")
        if line and _PASSWORD_LINE_RE.match(line):
            return line
    return None


def _is_password_sidecar_filename(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(".txt") and any(
        marker in lower for marker in _PASSWORD_FILENAME_MARKERS
    )


def _opened_zip(zip_path: Path) -> zipfile.ZipFile:
    return zipfile.ZipFile(zip_path, "r")


def _read_zip_member(archive: zipfile.ZipFile, name: str) -> str | None:
    try:
        info = archive.getinfo(name)
        if info.file_size > _MAX_READ_BYTES:
            return None
        with archive.open(name) as handle:
            return handle.read(_MAX_READ_BYTES).decode("utf-8", errors="replace")
    except (KeyError, OSError):
        return None


def detect_zip_passwords(zip_path: Path) -> tuple[dict[str, str], str | None]:
    """Detect 2FA passwords inside a ZIP archive.

    Returns ``(per_session, default)`` where *per_session* maps every
    ``.session`` member path (relative, POSIX) to its detected password,
    and *default* is a single shared password found at the archive root.
    """
    per_session: dict[str, str] = {}
    default_password: str | None = None

    try:
        archive = _opened_zip(zip_path)
    except (zipfile.BadZipFile, OSError):
        return per_session, default_password

    with archive:
        infos = archive.infolist()
        members = [Path(info.filename) for info in infos]
        name_set = {path.as_posix() for path in members}
        session_members = [
            member for member in members if member.suffix.lower() == ".session"
        ]
        if not session_members:
            return per_session, default_password

        for session in session_members:
            session_key = session.as_posix()
            parent = session.parent.as_posix() if session.parent.parts else ""

            for stem_candidate in (session.stem, session.stem.lower()):
                json_name = (
                    f"{parent}/{stem_candidate}.json"
                    if parent
                    else f"{stem_candidate}.json"
                )
                if json_name in name_set:
                    raw = _read_zip_member(archive, json_name)
                    if raw is not None:
                        try:
                            password = _walk_json_password(json.loads(raw))
                        except Exception:  # noqa: BLE001
                            password = None
                        if password:
                            per_session[session_key] = password
                    break

            if session_key in per_session:
                continue

            # Sidecar text files only match inside a real sub-folder (a
            # root-level ``2FA.txt``/``password.txt`` becomes the default).
            for candidate in members:
                if (
                    candidate.suffix.lower() != ".txt"
                    or candidate.parent != session.parent
                    or not candidate.parent.parts
                ):
                    continue
                if _is_password_sidecar_filename(candidate.name):
                    raw = _read_zip_member(archive, candidate.as_posix())
                    if raw is not None:
                        password = _extract_text_password(raw)
                        if password:
                            per_session[session_key] = password
                    break

            if default_password is None:
                root_texts = [
                    candidate
                    for candidate in members
                    if not candidate.parent.parts
                    and _is_password_sidecar_filename(candidate.name)
                ]
                if len(root_texts) == 1:
                    raw = _read_zip_member(archive, root_texts[0].as_posix())
                    if raw is not None:
                        default_password = _extract_text_password(raw)

    return per_session, default_password


def detect_adjacent_passwords(
    session_file: Path,
) -> tuple[dict[str, str], str | None]:
    """Detect sidecar passwords sitting next to a single ``.session`` file."""
    per_session: dict[str, str] = {}
    default_password: str | None = None
    session_dir = session_file.parent
    if not session_file.is_file() or not session_dir.is_dir():
        return per_session, default_password

    stem = session_file.stem
    for candidate in sorted(session_dir.iterdir()):
        if (
            candidate.is_file()
            and candidate.suffix.lower() == ".json"
            and candidate.stem == stem
        ):
            password = extract_password_from_json(candidate)
            if password:
                per_session[session_file.name] = password
                return per_session, default_password

    root_markers = [
        candidate
        for candidate in sorted(session_dir.iterdir())
        if candidate.is_file() and _is_password_sidecar_filename(candidate.name)
    ]
    if root_markers:
        password = extract_password_from_text(root_markers[0])
        if password:
            per_session[session_file.name] = password

    return per_session, default_password
