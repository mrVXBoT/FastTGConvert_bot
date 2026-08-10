"""fresh_session.py — Fresh Session migration service.

Logic:
1. Connect old session (proxy → local fallback) → get phone number.
2. Register OTP listener on old session for messages from Telegram (777000).
3. Send a code-request on a *new* Telethon client (random device, proxy → fallback).
4. Wait for the OTP to arrive on the old session via event.
5. Sign in the new client with that OTP (+ optional 2FA password).
6. [Optional] Change / remove 2FA password on the new session.
7. Kick ALL other authorizations (ResetAuthorizationsRequest) — invalidates old session.
8. Verify new session → store result.
9. Return FreshSessionResult with ZIP paths for new sessions and failed originals.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import tempfile
import time
import zipfile
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from app.services.device_params import get_stable_device_params
from app.services.file_merge import _is_valid_sqlite_session
from app.services.files import (
    MAX_COMPRESSION_RATIO,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_UNCOMPRESSED_BYTES,
    UnsafeArchiveError,
)
from app.services.jobs import JobCancelled, JobProgress
from app.services.session_to_tdata import _ensure_opentele_patched
from app.services.tdata_to_session import (
    convert_tdata_dir_to_sessions,
    extract_zip_tdata_safe,
    find_tdata_dirs,
)

# User-facing failure categories (mirrors the competitor's report).
FAILURE_CATEGORY_LABELS = {
    "frozen": "Frozen",
    "banned": "Banned",
    "wrong_password": "Wrong Password",
    "network_error": "Network Error",
    "revoked": "Revoked",
}

LOGGER = logging.getLogger(__name__)

OTP_WAIT_SECONDS = (
    25  # how long to wait for OTP from Telegram (normally arrives in 2-5s)
)
OTP_POLL_INTERVAL = 1.0  # polling interval while waiting for the OTP
TELETHON_TIMEOUT = 30  # connection / RPC timeout
PROXY_TIMEOUT = 10  # timeout used when trying proxy; falls back to direct

# Max concurrent migrations.
_FRESH_CONCURRENCY = 10


def _mask_phone(phone: str) -> str:
    """Mask the middle digits of a phone number for log safety (PII)."""
    digits = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    if len(digits) < 6:
        return "***"
    return f"{digits[:3]}...{digits[-2:]}"


# ── Data structures ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SessionFreshDetail:
    session_name: str
    status: str  # 'ok' | 'otp_timeout' | 'unauthorized' | '2fa_required' | 'error'
    phone: str
    message: str
    kicked: bool = False  # True if ResetAuthorizations succeeded
    category: str = (
        ""  # 'frozen' | 'banned' | 'wrong_password' | 'network_error' | 'revoked'
    )


@dataclass
class FreshSessionResult:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    kicked: int = 0  # number of sessions where kick succeeded
    details: list[SessionFreshDetail] = field(default_factory=list)
    new_sessions_zip: Path | None = None  # ZIP of newly created sessions
    failed_zip: Path | None = None  # ZIP of originals that failed


# ── Proxy-aware connect helper ────────────────────────────────────────────────


def _extract_zip_sessions_named(zip_path: Path, target_dir: Path) -> list[Path]:
    """Extract ``.session`` members preserving their relative folder paths.

    The relative path is kept so auto-detected per-account 2FA passwords
    (keyed by member path) map 1:1 to the extracted files.
    """
    with zipfile.ZipFile(zip_path, "r") as archive:
        members = archive.infolist()
        if len(members) > MAX_ZIP_MEMBERS:
            raise UnsafeArchiveError("zip_too_many_members")

        total_uncompressed = 0
        session_files: list[Path] = []
        for info in members:
            member_path = Path(info.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise UnsafeArchiveError("zip_unsafe_path")

            total_uncompressed += info.file_size
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise UnsafeArchiveError("zip_uncompressed_limit")

            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > MAX_COMPRESSION_RATIO:
                    raise UnsafeArchiveError("zip_suspicious_ratio")

            if member_path.suffix.lower() != ".session":
                continue
            dest = target_dir / member_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, dest.open("wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
            session_files.append(dest)

    return session_files


async def _connect_with_proxy_fallback(
    client: object,
    proxy: tuple | None,
    timeout: float = TELETHON_TIMEOUT,
) -> bool:
    """Connect *client* using *proxy*; fall back to direct on timeout/error.

    Returns True if connected via proxy, False if connected directly.
    The client object is mutated in place (its ``_proxy`` attribute is set).
    """
    if proxy is not None:
        try:
            client._proxy = proxy  # type: ignore[attr-defined]
            await asyncio.wait_for(client.connect(), timeout=PROXY_TIMEOUT)  # type: ignore[attr-defined]
            return True
        except Exception:  # noqa: BLE001
            # Proxy failed — disconnect silently and retry without proxy
            with suppress(Exception):
                await client.disconnect()  # type: ignore[attr-defined]
            client._proxy = None  # type: ignore[attr-defined]

    # Direct (local) connection
    await asyncio.wait_for(client.connect(), timeout=timeout)  # type: ignore[attr-defined]
    return False


# ── Core single-session migration ─────────────────────────────────────────────


async def freshen_single_session(
    session_file: Path,
    credentials: list[tuple[int, str]],
    output_dir: Path,
    *,
    password_2fa: str | None = None,
    new_password: str | None = None,
    remove_password: bool = False,
    proxy: tuple | None = None,
    password_map: dict[str, str] | None = None,
    default_password: str | None = None,
    password_rel: str | None = None,
) -> SessionFreshDetail:
    """Migrate one old .session to a brand-new .session file.

    Steps:
      1. Connect old session (proxy → local fallback) → read phone.
      2. Install OTP listener on old session.
      3. Connect new client (random device, proxy → local fallback).
      4. Send code-request via new_client.
      5. Await OTP from event queue.
      6. Sign-in new_client with OTP (+ optional 2FA password).
      7. [Optional] Change / remove 2FA on new session.
      8. Kick ALL other authorizations (invalidates old session + other devices).
      9. Verify & disconnect both.
    """
    session_name = session_file.name

    if not _is_valid_sqlite_session(session_file):
        return SessionFreshDetail(
            session_name=session_name,
            status="error",
            phone="",
            message="Invalid SQLite session (missing auth_key)",
        )

    # Auto-detected password resolution: manual input wins, then the
    # per-session sidecar (relative member path, then basename), then a
    # batch-wide default.
    if password_2fa is None or not password_2fa.strip():
        captured_map = password_map or {}
        password_2fa = captured_map.get(session_file.name)
        if password_2fa is None and password_rel is not None:
            password_2fa = captured_map.get(password_rel)
        if password_2fa is None:
            # Extracted ZIP sessions are named ``session_<idx>_<orig>``
            # (legacy flattening); the map may be keyed by the basename.
            stripped = re.sub(
                r"^session_\d+_(.+)$", r"\1", password_rel or session_file.name
            )
            password_2fa = captured_map.get(stripped)
        if password_2fa is None or not password_2fa.strip():
            password_2fa = default_password
    password_2fa = password_2fa or None

    try:
        from telethon import TelegramClient, functions  # type: ignore[import-untyped]
        from telethon.errors import (  # type: ignore[import-untyped]
            AuthKeyDuplicatedError,
            AuthKeyUnregisteredError,
            PasswordHashInvalidError,
            PhoneCodeExpiredError,
            PhoneCodeInvalidError,
            PhoneNumberBannedError,
            SessionExpiredError,
            SessionPasswordNeededError,
            SessionRevokedError,
            UserDeactivatedBanError,
            UserDeactivatedError,
        )

    except ModuleNotFoundError:
        return SessionFreshDetail(
            session_name=session_name,
            status="error",
            phone="",
            message="Telethon library missing",
        )

    phone = ""
    last_exc: Exception | None = None

    for api_id, api_hash in credentials:
        old_client = None
        new_client = None

        with tempfile.TemporaryDirectory(prefix="ftgc_fresh_") as tmp:
            tmp_path = Path(tmp)
            old_sess_path = tmp_path / "old_account.session"
            shutil.copy2(session_file, old_sess_path)
            old_stem = str(old_sess_path.with_suffix(""))

            try:
                # ── Step 1: connect old session (proxy → local fallback) ───
                old_device_kwargs = get_stable_device_params(session_file)
                old_client = TelegramClient(
                    old_stem,
                    api_id,
                    api_hash,
                    receive_updates=True,
                    **old_device_kwargs,
                )
                await _connect_with_proxy_fallback(old_client, proxy)

                if not await old_client.is_user_authorized():
                    LOGGER.info(
                        "Fresh session: session unauthorized/expired (%s)",
                        session_name,
                    )
                    return SessionFreshDetail(
                        session_name=session_name,
                        status="unauthorized",
                        phone="",
                        message="Session unauthorized or expired",
                    )

                me = await asyncio.wait_for(old_client.get_me(), timeout=30)
                phone = (me.phone or "").strip()
                if phone and not phone.startswith("+"):
                    phone = "+" + phone

                LOGGER.info(
                    "Fresh session: old session authorised (%s)",
                    session_name,
                )

                # ── Step 3: Create new client with stable device params ────
                # Name the new session by phone number; only when the profile
                # has no phone at all do we fall back to the source name.
                new_account_name = phone or Path(session_file).stem
                new_sess_path = output_dir / f"{new_account_name}.session"
                new_stem = str(new_sess_path.with_suffix(""))
                new_device_kwargs = get_stable_device_params(new_sess_path)

                new_client = TelegramClient(
                    new_stem,
                    api_id,
                    api_hash,
                    receive_updates=False,
                    **new_device_kwargs,
                )
                await _connect_with_proxy_fallback(new_client, proxy)

                # ── Step 4: Send code request ─────────────────────────────
                code_sent_at_ts = time.time()
                sent = await asyncio.wait_for(
                    new_client.send_code_request(phone), timeout=60
                )
                phone_code_hash = sent.phone_code_hash
                LOGGER.info("Code request sent for %s", session_name)

                # ── Step 5: Poll 777000 for OTP code via direct RPC ───────
                otp_code: str | None = None
                poll_deadline = time.time() + OTP_WAIT_SECONDS
                while time.time() < poll_deadline:
                    await asyncio.sleep(OTP_POLL_INTERVAL)
                    try:
                        msgs = await old_client.get_messages(777000, limit=3)
                        for m in msgs:
                            if (
                                m
                                and m.date
                                and m.date.timestamp() >= (code_sent_at_ts - 5)
                            ):
                                codes = re.findall(r"\b\d{5,6}\b", m.message or "")
                                if codes:
                                    otp_code = codes[0]
                                    LOGGER.info(
                                        "OTP code %s retrieved for %s",
                                        otp_code,
                                        session_name,
                                    )
                                    break
                        if otp_code:
                            break
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.warning(
                            "OTP fetch polling error for %s: %s", session_name, exc
                        )

                if not otp_code:
                    return SessionFreshDetail(
                        session_name=session_name,
                        status="otp_timeout",
                        phone=phone,
                        message=f"OTP not received within {OTP_WAIT_SECONDS}s",
                        category="network_error",
                    )

                # ── Step 6: Sign in new client ────────────────────────────
                try:
                    await asyncio.wait_for(
                        new_client.sign_in(
                            phone, otp_code, phone_code_hash=phone_code_hash
                        ),
                        timeout=60,
                    )
                except SessionPasswordNeededError:
                    if not password_2fa:
                        return SessionFreshDetail(
                            session_name=session_name,
                            status="2fa_required",
                            phone=phone,
                            message="2FA password required but not provided",
                        )
                    try:
                        await asyncio.wait_for(
                            new_client.sign_in(password=password_2fa), timeout=60
                        )
                    except PasswordHashInvalidError:
                        return SessionFreshDetail(
                            session_name=session_name,
                            status="2fa_required",
                            phone=phone,
                            message="Invalid 2FA password",
                            category="wrong_password",
                        )
                except (PhoneCodeInvalidError, PhoneCodeExpiredError) as exc:
                    return SessionFreshDetail(
                        session_name=session_name,
                        status="error",
                        phone=phone,
                        message=f"OTP error: {exc}",
                    )

                # ── Step 7: Verify new session ────────────────────────────
                # ── Step 8: Update / Remove 2FA on new session ────────────
                if new_password is not None or remove_password:
                    try:
                        cur_pwd = password_2fa if password_2fa else ""
                        if remove_password:
                            await new_client.edit_2fa(
                                current_password=cur_pwd, new_password=None
                            )
                        elif new_password:
                            await new_client.edit_2fa(
                                current_password=cur_pwd, new_password=new_password
                            )
                        LOGGER.info(
                            "Fresh session: 2FA updated for %s (remove=%s)",
                            session_name,
                            remove_password,
                        )
                    except Exception as exc:  # noqa: BLE001
                        # Non-fatal: session was created, just log the 2FA failure
                        LOGGER.warning(
                            "Fresh session: 2FA edit failed for %s: %s",
                            session_name,
                            exc,
                        )

                # ── Step 9: Invalidate old session and kick other authorizations ────
                kicked = False
                # Try resetting authorizations from new client
                try:
                    await asyncio.wait_for(
                        new_client(functions.auth.ResetAuthorizationsRequest()),
                        timeout=15,
                    )
                    kicked = True
                    LOGGER.info(
                        "Fresh session: reset authorizations on new client for %s",
                        session_name,
                    )
                except Exception as exc:  # noqa: BLE001
                    LOGGER.debug(
                        "Fresh session: reset authorizations on new client unavailable for %s: %s",
                        session_name,
                        exc,
                    )

                # Log out old session so the uploaded session file is invalidated on Telegram
                try:
                    await asyncio.wait_for(
                        old_client.log_out(),
                        timeout=15,
                    )
                    kicked = True
                    LOGGER.info(
                        "Fresh session: logged out old session for %s",
                        session_name,
                    )
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning(
                        "Fresh session: old session log_out failed for %s: %s",
                        session_name,
                        exc,
                    )

                LOGGER.info(
                    "Fresh session success: %s (%s) → %s",
                    session_name,
                    _mask_phone(phone),
                    new_sess_path.name,
                )
                return SessionFreshDetail(
                    session_name=session_name,
                    status="ok",
                    phone=phone,
                    message=f"New session created: {new_sess_path.name}",
                    kicked=kicked,
                )

            except PhoneNumberBannedError:
                return SessionFreshDetail(
                    session_name=session_name,
                    status="unauthorized",
                    phone=phone,
                    message="Phone number banned",
                    category="banned",
                )

            except (UserDeactivatedBanError, UserDeactivatedError):
                return SessionFreshDetail(
                    session_name=session_name,
                    status="unauthorized",
                    phone=phone,
                    message="Account frozen or deactivated",
                    category="frozen",
                )

            except (
                AuthKeyDuplicatedError,
                AuthKeyUnregisteredError,
                SessionExpiredError,
                SessionRevokedError,
            ):
                return SessionFreshDetail(
                    session_name=session_name,
                    status="unauthorized",
                    phone=phone,
                    message="Session revoked or expired",
                    category="revoked",
                )

            except Exception as exc:
                LOGGER.warning(
                    "Fresh session error (api_id=%d) %s: %s",
                    api_id,
                    session_name,
                    exc,
                    exc_info=True,
                )
                last_exc = exc
                continue
            finally:
                if old_client is not None:
                    with suppress(Exception):
                        await old_client.disconnect()
                if new_client is not None:
                    with suppress(Exception):
                        await new_client.disconnect()

    if last_exc is not None:
        is_network = isinstance(
            last_exc, (asyncio.TimeoutError, TimeoutError, OSError, ConnectionError)
        )
        return SessionFreshDetail(
            session_name=session_name,
            status="error",
            phone=phone or "",
            message=(
                f"Network error: {type(last_exc).__name__}"
                if is_network
                else f"Error: {type(last_exc).__name__}"
            ),
            category="network_error" if is_network else "",
        )

    return SessionFreshDetail(
        session_name=session_name,
        status="unauthorized",
        phone=phone or "",
        message="Session unauthorized or expired across all credentials",
    )


# ── Batch orchestrator ────────────────────────────────────────────────────────


async def process_fresh_sessions(
    input_path: Path,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
    password_2fa: str | None = None,
    new_password: str | None = None,
    remove_password: bool = False,
    proxy: tuple | None = None,
    progress: JobProgress | None = None,
    cancel_event: asyncio.Event | None = None,
    password_map: dict[str, str] | None = None,
    default_password: str | None = None,
) -> FreshSessionResult:
    """Extract sessions (or TData) from ZIP or single .session and re-authenticate.

    Args:
        input_path:      Path to the uploaded file.
        credentials:     List of (api_id, api_hash) pairs to try.
        original_name:   Original filename (used to determine ZIP vs. .session).
        password_2fa:    Existing 2FA password (used for sign-in).
        new_password:    New 2FA password to set after migration (None = keep old).
        remove_password: If True, 2FA is disabled on the new session.
        proxy:           Telethon proxy tuple; falls back to direct on timeout.
        progress:        JobProgress instance for live progress reporting.
        cancel_event:    asyncio.Event; set to cancel the batch.
        password_map:    Auto-detected per-session password map (session basename).
        default_password: Batch-wide password applied when no per-session match.

    Returns:
        FreshSessionResult with ZIPs and per-session details.
    """
    _ensure_opentele_patched()

    input_tmp: tempfile.TemporaryDirectory[str] | None = None
    new_dir: tempfile.TemporaryDirectory[str] | None = None
    failed_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []
    result = FreshSessionResult()

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()

        # ── Unpack input (sessions or TData) ─────────────────────────────
        if suffix == ".zip":
            input_tmp = tempfile.TemporaryDirectory(prefix="ftgc_fresh_zip_")
            work_path = Path(input_tmp.name)
            session_files = await asyncio.to_thread(
                _extract_zip_sessions_named, input_path, work_path
            )
            if not session_files:
                tdata_work = work_path / "_tdata"
                tdata_work.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(extract_zip_tdata_safe, input_path, tdata_work)
                tdata_dirs = await asyncio.to_thread(find_tdata_dirs, tdata_work)
                converted_dir = work_path / "_converted"
                converted_dir.mkdir(parents=True, exist_ok=True)
                for t_dir in tdata_dirs:
                    out_sessions = await convert_tdata_dir_to_sessions(
                        t_dir, converted_dir
                    )
                    session_files.extend(out_sessions)
        elif suffix == ".session":
            if original_name:
                input_tmp = tempfile.TemporaryDirectory(prefix="ftgc_fresh_one_")
                copied = Path(input_tmp.name) / Path(original_name).name
                shutil.copy2(input_path, copied)
                session_files = [copied]
            else:
                session_files = [input_path]

        result.total = len(session_files)
        if result.total == 0:
            return result

        # ── Output directories ────────────────────────────────────────────
        new_dir = tempfile.TemporaryDirectory(prefix="ftgc_fresh_new_")
        failed_dir = tempfile.TemporaryDirectory(prefix="ftgc_fresh_fail_")

        new_dir_path = Path(new_dir.name)
        failed_dir_path = Path(failed_dir.name)

        if progress is not None:
            progress.total = len(session_files)

        fresh_semaphore = asyncio.Semaphore(
            min(_FRESH_CONCURRENCY, len(session_files) or 1)
        )

        async def freshen_one(index: int) -> SessionFreshDetail:
            if cancel_event is not None and cancel_event.is_set():
                raise JobCancelled()
            async with fresh_semaphore:
                session_file = session_files[index]
                password_rel: str | None = None
                if input_tmp is not None:
                    try:
                        password_rel = session_file.relative_to(
                            Path(input_tmp.name)
                        ).as_posix()
                    except ValueError:
                        password_rel = None
                return await freshen_single_session(
                    session_file,
                    credentials,
                    new_dir_path,
                    password_2fa=password_2fa,
                    new_password=new_password,
                    remove_password=remove_password,
                    proxy=proxy,
                    password_map=password_map,
                    default_password=default_password,
                    password_rel=password_rel,
                )

        async def tracked_freshen(index: int) -> SessionFreshDetail:
            detail = await freshen_one(index)
            if progress is not None:
                progress.done += 1
            return detail

        details = await asyncio.gather(
            *(tracked_freshen(index) for index in range(len(session_files)))
        )

        for index, detail in enumerate(details):
            result.details.append(detail)

            if detail.status == "ok":
                result.succeeded += 1
                if detail.kicked:
                    result.kicked += 1
            else:
                result.failed += 1
                # Copy original to failed dir for user to download
                dest = failed_dir_path / session_files[index].name
                with suppress(Exception):
                    shutil.copy2(session_files[index], dest)

        # ── Pack new sessions ZIP ─────────────────────────────────────────
        new_sess_files = list(new_dir_path.glob("*.session"))
        if new_sess_files:
            new_zip_path = (
                Path(tempfile.gettempdir()) / f"ftgc_fresh_new_{uuid4().hex}.zip"
            )
            with zipfile.ZipFile(new_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in new_sess_files:
                    zf.write(f, f.name)
            result.new_sessions_zip = new_zip_path

        # ── Pack failed sessions ZIP ──────────────────────────────────────
        failed_files = list(failed_dir_path.glob("*.session"))
        if failed_files:
            fail_zip_path = (
                Path(tempfile.gettempdir()) / f"ftgc_fresh_fail_{uuid4().hex}.zip"
            )
            with zipfile.ZipFile(fail_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in failed_files:
                    zf.write(f, f.name)
            result.failed_zip = fail_zip_path

        return result

    finally:
        for td in (input_tmp, new_dir, failed_dir):
            if td is not None:
                with suppress(Exception):
                    td.cleanup()
