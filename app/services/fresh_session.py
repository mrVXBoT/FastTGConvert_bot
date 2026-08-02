"""fresh_session.py — Fresh Session migration service.

Logic (adapted from SessionBackup.py):
1. Connect old session → get phone number + country code.
2. Register an event listener on old session for messages from Telegram (777000).
3. Send a code-request to the same phone number on a *new* Telethon client.
4. Wait for the OTP to arrive on the old session via event.
5. Sign in the new client with that OTP (+ optional 2FA password).
6. Verify new session → store result.
7. Return FreshSessionResult with ZIP paths for new sessions and failed originals.
"""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
import tempfile
import zipfile
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from app.services.contacts_checker import extract_zip_sessions_safe
from app.services.file_merge import _is_valid_sqlite_session
from app.services.session_to_tdata import _ensure_opentele_patched

LOGGER = logging.getLogger(__name__)

OTP_WAIT_SECONDS = 90  # how long to wait for OTP from Telegram
TELETHON_TIMEOUT = 60


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SessionFreshDetail:
    session_name: str
    status: str          # 'ok' | 'otp_timeout' | 'unauthorized' | '2fa_required' | 'error'
    phone: str
    message: str


@dataclass
class FreshSessionResult:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    details: list[SessionFreshDetail] = field(default_factory=list)
    new_sessions_zip: Path | None = None   # ZIP of newly created sessions
    failed_zip: Path | None = None         # ZIP of originals that failed


# ── Core single-session migration ────────────────────────────────────────────

async def freshen_single_session(
    session_file: Path,
    credentials: list[tuple[int, str]],
    output_dir: Path,
    *,
    password_2fa: str | None = None,
) -> SessionFreshDetail:
    """Migrate one old .session to a brand-new .session file.

    Steps:
      1. Connect old session → read phone.
      2. Install OTP event listener on old session (listens for Telegram 777000).
      3. Send code-request via new_client.
      4. Await OTP from event queue.
      5. Sign-in new_client with OTP.
      6. Verify & disconnect both.
    """
    session_name = session_file.name

    if not _is_valid_sqlite_session(session_file):
        return SessionFreshDetail(
            session_name=session_name,
            status="error",
            phone="",
            message="Invalid SQLite session (missing auth_key)",
        )

    try:
        from telethon import TelegramClient, events  # type: ignore[import-untyped]
        from telethon.errors import (  # type: ignore[import-untyped]
            AuthKeyUnregisteredError,
            PhoneCodeExpiredError,
            PhoneCodeInvalidError,
            SessionPasswordNeededError,
            SessionRevokedError,
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

    for api_id, api_hash in credentials:
        old_client = None
        new_client = None

        with tempfile.TemporaryDirectory(prefix="ftgc_fresh_") as tmp:
            tmp_path = Path(tmp)
            old_sess_path = tmp_path / "old_account.session"
            shutil.copy2(session_file, old_sess_path)
            old_stem = str(old_sess_path.with_suffix(""))

            try:
                # ── Step 1: read phone from old session ───────────────────
                old_client = TelegramClient(
                    old_stem, api_id, api_hash, receive_updates=True
                )
                await asyncio.wait_for(old_client.connect(), timeout=TELETHON_TIMEOUT)

                if not await old_client.is_user_authorized():
                    return SessionFreshDetail(
                        session_name=session_name,
                        status="unauthorized",
                        phone="",
                        message="Session is unauthorized or expired",
                    )

                me = await asyncio.wait_for(old_client.get_me(), timeout=30)
                phone = me.phone or str(me.id)
                if not phone.startswith("+"):
                    phone = "+" + phone

                LOGGER.info("Fresh session: old session is %s (%s)", me.first_name, phone)

                # ── Step 2: OTP event listener on old session ─────────────
                otp_queue: asyncio.Queue[str] = asyncio.Queue()

                @old_client.on(events.NewMessage(from_users=777000))
                async def _otp_handler(
                    event: events.NewMessage.Event,
                    _q: asyncio.Queue[str] = otp_queue,
                ) -> None:
                    text = event.message.message or ""
                    codes = re.findall(r"\b\d{5,6}\b", text)
                    if codes:
                        LOGGER.info("OTP received for %s: %s", session_name, codes[0])
                        await _q.put(codes[0])

                # Client is already connected & authorized — events dispatch after connect()

                # ── Step 3: Create new session & send code request ────────
                new_sess_path = output_dir / f"{phone}.session"
                new_stem = str(new_sess_path.with_suffix(""))

                new_client = TelegramClient(new_stem, api_id, api_hash, receive_updates=False)
                await asyncio.wait_for(new_client.connect(), timeout=TELETHON_TIMEOUT)

                sent = await asyncio.wait_for(
                    new_client.send_code_request(phone), timeout=60
                )
                phone_code_hash = sent.phone_code_hash
                LOGGER.info("Code request sent to %s for %s", phone, session_name)

                # ── Step 4: Wait for OTP ──────────────────────────────────
                try:
                    otp_code = await asyncio.wait_for(
                        otp_queue.get(), timeout=OTP_WAIT_SECONDS
                    )
                except TimeoutError:
                    return SessionFreshDetail(
                        session_name=session_name,
                        status="otp_timeout",
                        phone=phone,
                        message=f"OTP not received within {OTP_WAIT_SECONDS}s",
                    )

                # ── Step 5: Sign in new client ────────────────────────────
                try:
                    await asyncio.wait_for(
                        new_client.sign_in(phone, otp_code, phone_code_hash=phone_code_hash),
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
                    await asyncio.wait_for(
                        new_client.sign_in(password=password_2fa), timeout=60
                    )
                except (PhoneCodeInvalidError, PhoneCodeExpiredError) as exc:
                    return SessionFreshDetail(
                        session_name=session_name,
                        status="error",
                        phone=phone,
                        message=f"OTP error: {exc}",
                    )

                # ── Step 6: Verify new session ────────────────────────────
                new_me = await asyncio.wait_for(new_client.get_me(), timeout=30)
                if not new_me:
                    return SessionFreshDetail(
                        session_name=session_name,
                        status="error",
                        phone=phone,
                        message="New session verification failed",
                    )

                LOGGER.info(
                    "Fresh session success: %s (%s) → %s",
                    session_name, phone, new_sess_path.name,
                )
                return SessionFreshDetail(
                    session_name=session_name,
                    status="ok",
                    phone=phone,
                    message=f"New session created: {new_sess_path.name}",
                )

            except (AuthKeyUnregisteredError, SessionRevokedError, UserDeactivatedError):
                return SessionFreshDetail(
                    session_name=session_name,
                    status="unauthorized",
                    phone=phone,
                    message="Session revoked or account deactivated",
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Fresh session error (api_id=%d) %s: %s", api_id, session_name, exc)
                continue
            finally:
                if old_client is not None:
                    with suppress(Exception):
                        old_client.remove_event_handler(_otp_handler, events.NewMessage)  # type: ignore[possibly-undefined]
                    with suppress(Exception):
                        await old_client.disconnect()
                if new_client is not None:
                    with suppress(Exception):
                        await new_client.disconnect()

    return SessionFreshDetail(
        session_name=session_name,
        status="error",
        phone=phone,
        message="Connection failed across all credentials",
    )


# ── Batch orchestrator ────────────────────────────────────────────────────────

async def process_fresh_sessions(
    input_path: Path,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
    password_2fa: str | None = None,
) -> FreshSessionResult:
    """Extract sessions from ZIP or single .session and re-authenticate each one.

    Returns a FreshSessionResult containing:
    - new_sessions_zip: ZIP of freshly created sessions (phone.session)
    - failed_zip:       ZIP of original files that could not be migrated
    - per-session details
    """
    _ensure_opentele_patched()

    input_tmp: tempfile.TemporaryDirectory[str] | None = None
    new_dir: tempfile.TemporaryDirectory[str] | None = None
    failed_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []

    result = FreshSessionResult()

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()

        # ── Unpack input ──────────────────────────────────────────────────
        if suffix == ".zip":
            input_tmp = tempfile.TemporaryDirectory(prefix="ftgc_fresh_zip_")
            session_files = extract_zip_sessions_safe(
                input_path, Path(input_tmp.name)
            )
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

        # ── Process sessions (sequentially to avoid flood) ────────────────
        # Note: sequential by design — concurrent OTP listeners on the same
        # phone pool can cause Telegram FloodWait very quickly.
        for sess_file in session_files:
            detail = await freshen_single_session(
                sess_file,
                credentials,
                new_dir_path,
                password_2fa=password_2fa,
            )
            result.details.append(detail)

            if detail.status == "ok":
                result.succeeded += 1
            else:
                result.failed += 1
                # Copy original to failed dir for user to download
                dest = failed_dir_path / sess_file.name
                with suppress(Exception):
                    shutil.copy2(sess_file, dest)

        # ── Pack new sessions ZIP ─────────────────────────────────────────
        new_sess_files = list(new_dir_path.glob("*.session"))
        if new_sess_files:
            new_zip_path = Path(tempfile.gettempdir()) / f"ftgc_fresh_new_{uuid4().hex}.zip"
            with zipfile.ZipFile(new_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in new_sess_files:
                    zf.write(f, f.name)
            result.new_sessions_zip = new_zip_path

        # ── Pack failed sessions ZIP ──────────────────────────────────────
        failed_files = list(failed_dir_path.glob("*.session"))
        if failed_files:
            fail_zip_path = Path(tempfile.gettempdir()) / f"ftgc_fresh_fail_{uuid4().hex}.zip"
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
