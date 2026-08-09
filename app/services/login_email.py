import asyncio
import logging
import random
import re
import shutil
import string
import tempfile
import zipfile
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiohttp
from telethon import TelegramClient, functions, types
from telethon.errors import (
    AuthKeyDuplicatedError,
    AuthKeyUnregisteredError,
    FloodWaitError,
    PhoneNumberBannedError,
    SessionExpiredError,
    SessionRevokedError,
    UserDeactivatedBanError,
    UserDeactivatedError,
)

from app.services.contacts_checker import extract_zip_sessions_safe
from app.services.device_params import get_stable_device_params
from app.services.jobs import JobCancelled, JobProgress

LOGGER = logging.getLogger(__name__)


@dataclass
class LoginEmailDetail:
    session_name: str
    phone: str
    status: str  # "changed", "no_email", "unauthorized", "error"
    old_email_pattern: str | None = None
    new_email: str | None = None
    message: str = ""


@dataclass
class LoginEmailBatchResult:
    total: int = 0
    changed_count: int = 0
    no_email_count: int = 0
    error_count: int = 0
    details: list[LoginEmailDetail] = field(default_factory=list)
    success_zip: Path | None = None
    failed_zip: Path | None = None
    failed_session_zip: Path | None = None
    classified_zip: Path | None = None


async def _create_mail_tm_account(
    session_http: aiohttp.ClientSession,
    retries: int = 3,
) -> tuple[str, str] | None:
    """Create a temporary disposable email address via Mail.tm API with retry mechanism."""
    for attempt in range(1, retries + 1):
        try:
            async with session_http.get(
                "https://api.mail.tm/domains", timeout=aiohttp.ClientTimeout(total=10)
            ) as res:
                if res.status != 200:
                    await asyncio.sleep(1)
                    continue
                data = await res.json()
                members = data.get("hydra:member", [])
                active_domains = [
                    m["domain"] for m in members if m.get("isActive", True)
                ]
                if not active_domains:
                    await asyncio.sleep(1)
                    continue
                domain = random.choice(active_domains)

            username = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=10)
            )
            address = f"{username}@{domain}"
            password = "Pass_" + "".join(
                random.choices(string.ascii_letters + string.digits, k=12)
            )

            async with session_http.post(
                "https://api.mail.tm/accounts",
                json={"address": address, "password": password},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as acc_res:
                if acc_res.status not in (200, 201):
                    await asyncio.sleep(1)
                    continue

            async with session_http.post(
                "https://api.mail.tm/token",
                json={"address": address, "password": password},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as tok_res:
                if tok_res.status != 200:
                    await asyncio.sleep(1)
                    continue
                tok_data = await tok_res.json()
                token = tok_data.get("token")
                if token:
                    return address, token
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                "Mail.tm account creation attempt %d failed: %s", attempt, exc
            )
            await asyncio.sleep(1)

    return None


async def _poll_mail_tm_otp(
    session_http: aiohttp.ClientSession, token: str, timeout: int = 25
) -> str | None:
    """Poll Mail.tm inbox for Telegram verification OTP code."""
    headers = {"Authorization": f"Bearer {token}"}
    start_time = asyncio.get_event_loop().time()

    while asyncio.get_event_loop().time() - start_time < timeout:
        try:
            async with session_http.get(
                "https://api.mail.tm/messages",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as res:
                if res.status == 200:
                    data = await res.json()
                    msgs = data.get("hydra:member", [])
                    if msgs:
                        msg_id = msgs[0]["id"]
                        async with session_http.get(
                            f"https://api.mail.tm/messages/{msg_id}",
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=10),
                        ) as msg_res:
                            if msg_res.status == 200:
                                msg_detail = await msg_res.json()
                                text = msg_detail.get("text", "") or msg_detail.get(
                                    "intro", ""
                                )
                                match = re.search(r"\b(\d{5,6})\b", text)
                                if match:
                                    return match.group(1)
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Mail.tm inbox polling error: %s", exc)

        await asyncio.sleep(2)

    return None


async def process_single_login_email(
    session_file: Path,
    credentials: list[tuple[int, str]],
    session_http: aiohttp.ClientSession,
    *,
    job_progress: JobProgress | None = None,
    max_flood_wait: int = 400,
    max_flood_retries: int = 3,
) -> LoginEmailDetail:
    """Inspect and update login email for a single session file."""
    session_name = session_file.stem
    phone = ""

    for api_id, api_hash in credentials:
        client = None
        try:
            device_kwargs = get_stable_device_params(session_file)
            client = TelegramClient(
                str(session_file.with_suffix("")),
                api_id,
                api_hash,
                **device_kwargs,
            )
            await asyncio.wait_for(client.connect(), timeout=15)

            if not await client.is_user_authorized():
                return LoginEmailDetail(
                    session_name=session_name,
                    phone=phone,
                    status="unauthorized",
                    message="Session not authorized",
                )

            me = await client.get_me()
            phone = getattr(me, "phone", "") or ""

            pwd_res = await client(functions.account.GetPasswordRequest())
            old_pattern = getattr(pwd_res, "login_email_pattern", None)

            if not old_pattern:
                return LoginEmailDetail(
                    session_name=session_name,
                    phone=phone,
                    status="no_email",
                    old_email_pattern=None,
                    message="No login email set on account",
                )

            # Create disposable temp email
            mail_tuple = await _create_mail_tm_account(session_http)
            if not mail_tuple:
                return LoginEmailDetail(
                    session_name=session_name,
                    phone=phone,
                    status="error",
                    old_email_pattern=old_pattern,
                    message="Could not create disposable email",
                )

            new_email, mail_token = mail_tuple
            purpose = types.EmailVerifyPurposeLoginChange()

            # Request verification code from Telegram (with automatic FloodWait retry)
            code_sent = False
            for attempt in range(1, max_flood_retries + 1):
                if job_progress and job_progress.cancel_requested:
                    raise JobCancelled("Operation cancelled")
                try:
                    await asyncio.wait_for(
                        client(
                            functions.account.SendVerifyEmailCodeRequest(
                                purpose=purpose, email=new_email
                            )
                        ),
                        timeout=15,
                    )
                    code_sent = True
                    break
                except FloodWaitError as exc:
                    seconds = getattr(exc, "seconds", 0)
                    if seconds <= max_flood_wait:
                        LOGGER.info(
                            "FloodWait of %ds for session %s. Auto-waiting before retry (attempt %d/%d)...",
                            seconds,
                            session_name,
                            attempt,
                            max_flood_retries,
                        )
                        for _ in range(seconds + 1):
                            if job_progress and job_progress.cancel_requested:
                                raise JobCancelled("Operation cancelled")
                            await asyncio.sleep(1)
                    else:
                        return LoginEmailDetail(
                            session_name=session_name,
                            phone=phone,
                            status="error",
                            old_email_pattern=old_pattern,
                            message=f"Telegram limit: Must wait {seconds}s required",
                        )

            if not code_sent:
                return LoginEmailDetail(
                    session_name=session_name,
                    phone=phone,
                    status="error",
                    old_email_pattern=old_pattern,
                    message="FloodWait retry count exceeded",
                )

            # Poll OTP code from email inbox
            otp_code = await _poll_mail_tm_otp(session_http, mail_token, timeout=25)
            if not otp_code:
                return LoginEmailDetail(
                    session_name=session_name,
                    phone=phone,
                    status="error",
                    old_email_pattern=old_pattern,
                    new_email=new_email,
                    message="OTP code polling timed out",
                )

            # Verify email code with Telegram
            await asyncio.wait_for(
                client(
                    functions.account.VerifyEmailRequest(
                        purpose=purpose,
                        verification=types.EmailVerificationCode(code=otp_code),
                    )
                ),
                timeout=15,
            )

            return LoginEmailDetail(
                session_name=session_name,
                phone=phone,
                status="changed",
                old_email_pattern=old_pattern,
                new_email=new_email,
                message="Login email successfully updated",
            )

        except (
            AuthKeyDuplicatedError,
            AuthKeyUnregisteredError,
            SessionExpiredError,
            SessionRevokedError,
            UserDeactivatedBanError,
            UserDeactivatedError,
            PhoneNumberBannedError,
        ):
            return LoginEmailDetail(
                session_name=session_name,
                phone=phone,
                status="unauthorized",
                message="Session revoked or account deactivated",
            )
        except FloodWaitError as exc:
            seconds = getattr(exc, "seconds", 0)
            LOGGER.warning(
                "FloodWait of %ds for session %s on SendVerifyEmailCodeRequest",
                seconds,
                session_name,
            )
            return LoginEmailDetail(
                session_name=session_name,
                phone=phone,
                status="error",
                old_email_pattern=old_pattern,
                message=f"Telegram limit: Must wait {seconds}s before requesting code again",
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Login email error for %s: %s", session_name, exc)
            continue
        finally:
            if client is not None:
                with suppress(Exception):
                    await client.disconnect()

    return LoginEmailDetail(
        session_name=session_name,
        phone=phone,
        status="error",
        message="Login email change failed for all credentials",
    )


async def process_batch_login_email(
    input_path: Path,
    credentials: list[tuple[int, str]],
    output_dir: Path,
    *,
    progress_callback: Callable[[JobProgress], Any] | None = None,
    job_progress: JobProgress | None = None,
) -> LoginEmailBatchResult:
    """Process a batch zip archive or single session for login email management."""
    result = LoginEmailBatchResult()

    if not credentials:
        LOGGER.error("No API credentials provided for login email batch")
        return result

    if job_progress is None:
        job_progress = JobProgress()

    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ftgc_email_") as tmp:
        tmp_dir = Path(tmp)

        if input_path.suffix.lower() == ".zip":
            extract_target = tmp_dir / "sessions"
            extract_zip_sessions_safe(input_path, extract_target)
            session_files = list(extract_target.rglob("*.session"))
        elif input_path.suffix.lower() == ".session":
            target = tmp_dir / "sessions" / input_path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_path, target)
            session_files = [target]
        else:
            return result

        result.total = len(session_files)
        job_progress.total = result.total
        job_progress.total_accounts = result.total

        if result.total == 0:
            return result

        success_dir = tmp_dir / "success_files"
        no_email_dir = tmp_dir / "no_email_files"
        failed_dir = tmp_dir / "failed_files"
        classified_dir = tmp_dir / "classified_files"
        success_dir.mkdir(exist_ok=True)
        no_email_dir.mkdir(exist_ok=True)
        failed_dir.mkdir(exist_ok=True)
        classified_dir.mkdir(exist_ok=True)
        report_lines: list[str] = ["# Login Email Change Report"]
        report_lines.append("name | status | phone | note")

        async with aiohttp.ClientSession() as session_http:
            for idx, sess_file in enumerate(session_files, start=1):
                if job_progress.cancel_requested:
                    raise JobCancelled("Login email processing cancelled by user")

                detail = await process_single_login_email(
                    sess_file,
                    credentials,
                    session_http,
                    job_progress=job_progress,
                )
                result.details.append(detail)
                note = detail.message.replace("|", "/")[:60]

                sess_name = sess_file.name
                if detail.status == "changed":
                    result.changed_count += 1
                    shutil.copy2(sess_file, success_dir / sess_name)
                    updated_dir = classified_dir / "updated"
                    updated_dir.mkdir(exist_ok=True)
                    shutil.copy2(sess_file, updated_dir / sess_name)
                elif detail.status == "no_email":
                    result.no_email_count += 1
                    shutil.copy2(sess_file, no_email_dir / sess_name)
                    no_login_dir = classified_dir / "no_login_email"
                    no_login_dir.mkdir(exist_ok=True)
                    shutil.copy2(sess_file, no_login_dir / sess_name)
                else:
                    result.error_count += 1
                    shutil.copy2(sess_file, failed_dir / sess_name)
                    failed_cls = classified_dir / "failed"
                    failed_cls.mkdir(exist_ok=True)
                    shutil.copy2(sess_file, failed_cls / sess_name)

                report_lines.append(
                    f"{sess_name} | {detail.status} | {detail.phone or ''} | {note}"
                )

                job_progress.done = idx
                job_progress.processed_accounts = idx
                if progress_callback:
                    with suppress(Exception):
                        res_p = progress_callback(job_progress)
                        if asyncio.iscoroutine(res_p):
                            await res_p

        # Build ZIP archives (English naming, consistent with the rest of the bot).
        token = uuid4().hex[:8]
        if result.changed_count > 0:
            succ_zip = (
                output_dir / f"Login_Email_Updated_{result.changed_count}_{token}.zip"
            )
            with zipfile.ZipFile(succ_zip, "w", zipfile.ZIP_DEFLATED) as z:
                for f in success_dir.glob("*.session"):
                    z.write(f, arcname=f.name)
            result.success_zip = succ_zip

        if result.no_email_count > 0:
            fail_zip = (
                output_dir / f"Login_Email_NoEmail_{result.no_email_count}_{token}.zip"
            )
            with zipfile.ZipFile(fail_zip, "w", zipfile.ZIP_DEFLATED) as z:
                for f in no_email_dir.glob("*.session"):
                    z.write(f, arcname=f.name)
            result.failed_zip = fail_zip

        if result.error_count > 0:
            err_zip = (
                output_dir / f"Login_Email_Failed_{result.error_count}_{token}.zip"
            )
            with zipfile.ZipFile(err_zip, "w", zipfile.ZIP_DEFLATED) as z:
                for f in failed_dir.glob("*.session"):
                    z.write(f, arcname=f.name)
            result.failed_session_zip = err_zip

        if result.total > 0:
            class_zip = output_dir / f"Login_Email_Classified_{token}.zip"
            with zipfile.ZipFile(class_zip, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("report.txt", "\n".join(report_lines) + "\n")
                for root, _, files in shutil.os.walk(classified_dir):
                    for file_name in files:
                        full_path = Path(root) / file_name
                        rel_path = full_path.relative_to(classified_dir)
                        z.write(full_path, arcname=str(rel_path))
            result.classified_zip = class_zip

    return result
