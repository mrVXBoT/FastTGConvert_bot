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


_MAIL_CREATION_LOCK = asyncio.Lock()
_DOMAINS_CACHE: list[str] = []
_DOMAINS_LOCK = asyncio.Lock()


async def _get_active_domains(session_http: aiohttp.ClientSession) -> list[str]:
    """Fetch and cache active email domains from Mail.tm."""
    global _DOMAINS_CACHE
    if _DOMAINS_CACHE:
        return _DOMAINS_CACHE
    async with _DOMAINS_LOCK:
        if _DOMAINS_CACHE:
            return _DOMAINS_CACHE
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            async with session_http.get(
                "https://api.mail.tm/domains",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as res:
                if res.status == 200:
                    data = await res.json()
                    _DOMAINS_CACHE = [
                        m["domain"]
                        for m in data.get("hydra:member", [])
                        if m.get("isActive", True)
                    ]
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Error fetching Mail.tm domains: %s", exc)
    return _DOMAINS_CACHE or ["emalupe.com"]


async def _create_mail_account_single(
    session_http: aiohttp.ClientSession,
    base_url: str = "https://api.mail.tm",
    retries: int = 8,
) -> tuple[str, str, str] | None:
    """Create a temporary email with automatic Mail.gw fallback on rate limit."""
    current_url = base_url

    domains = await _get_active_domains(session_http)
    if not domains:
        domains = ["emalupe.com"]

    headers = {"User-Agent": "Mozilla/5.0"}

    for attempt in range(1, retries + 1):
        domain = random.choice(domains)
        username = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        address = f"{username}@{domain}"
        password = "Pass_" + "".join(
            random.choices(string.ascii_letters + string.digits, k=12)
        )

        async with _MAIL_CREATION_LOCK:
            await asyncio.sleep(0.25)
            try:
                async with session_http.post(
                    f"{current_url}/accounts",
                    headers=headers,
                    json={"address": address, "password": password},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as acc_res:
                    if acc_res.status == 429:
                        current_url = (
                            "https://api.mail.gw"
                            if current_url == "https://api.mail.tm"
                            else "https://api.mail.tm"
                        )
                        await asyncio.sleep(0.2)
                        continue
                    if acc_res.status not in (200, 201):
                        await asyncio.sleep(0.1)
                        continue
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Account POST error on %s: %s", current_url, exc)
                await asyncio.sleep(0.1)
                continue

        try:
            async with session_http.post(
                f"{current_url}/token",
                headers=headers,
                json={"address": address, "password": password},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as tok_res:
                if tok_res.status == 200:
                    tok_data = await tok_res.json()
                    token = tok_data.get("token")
                    if token:
                        return address, token, current_url
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Token POST error on %s: %s", current_url, exc)

        await asyncio.sleep(0.1)

    return None


async def _create_tempmail_lol_account(
    session_http: aiohttp.ClientSession,
) -> tuple[str, str, str] | None:
    """Create a temporary email via tempmail.lol API."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with session_http.get(
            "https://api.tempmail.lol/v2/inbox/create",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=5),
        ) as res:
            if res.status in (200, 201):
                data = await res.json()
                address = data.get("address")
                token = data.get("token")
                if address and token:
                    return address, token, "https://api.tempmail.lol"
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("tempmail.lol creation error: %s", exc)
    return None


async def _create_mail_tm_account(
    session_http: aiohttp.ClientSession,
) -> tuple[str, str, str] | None:
    """Create a temporary disposable email address trying tempmail.lol, then Mail.tm, then Mail.gw."""
    res = await _create_tempmail_lol_account(session_http)
    if res:
        return res
    return await _create_mail_account_single(
        session_http, base_url="https://api.mail.tm"
    )


async def _poll_mail_tm_otp(
    session_http: aiohttp.ClientSession,
    token: str,
    timeout: int = 25,
    base_url: str = "https://api.mail.tm",
) -> str | None:
    """Poll tempmail.lol / Mail.tm / Mail.gw inbox for Telegram verification OTP code."""
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0"}
    start_time = asyncio.get_event_loop().time()

    if "tempmail.lol" in base_url:
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                async with session_http.get(
                    f"https://api.tempmail.lol/v2/inbox?token={token}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as res:
                    if res.status == 200:
                        data = await res.json()
                        emails = data.get("emails", [])
                        for em in emails:
                            text = (
                                (em.get("body") or "")
                                + " "
                                + (em.get("html") or "")
                                + " "
                                + (em.get("subject") or "")
                            )
                            match = re.search(r"\b(\d{5,6})\b", text)
                            if match:
                                return match.group(1)
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("tempmail.lol polling error: %s", exc)

            await asyncio.sleep(0.3)
        return None

    while asyncio.get_event_loop().time() - start_time < timeout:
        try:
            async with session_http.get(
                f"{base_url}/messages",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as res:
                if res.status == 200:
                    data = await res.json()
                    msgs = data.get("hydra:member", [])
                    if msgs:
                        msg_id = msgs[0]["id"]
                        async with session_http.get(
                            f"{base_url}/messages/{msg_id}",
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=5),
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
            LOGGER.debug("Mail inbox polling error: %s", exc)

        await asyncio.sleep(0.2)

    return None


_RUNTIME_EXTRA_CREDENTIALS: list[tuple[int, str]] = []


def _append_api_credential_to_env(api_id: int, api_hash: str) -> None:
    """Safely append a newly generated API credential pair to .env file and runtime memory."""
    pair_tuple = (api_id, api_hash)
    if pair_tuple not in _RUNTIME_EXTRA_CREDENTIALS:
        _RUNTIME_EXTRA_CREDENTIALS.append(pair_tuple)

    pair_str = f"{api_id}:{api_hash}"
    env_path = Path(".env")
    if not env_path.exists():
        return

    try:
        content = env_path.read_text(encoding="utf-8")
        if pair_str in content:
            return

        lines = content.splitlines()
        updated = False
        new_lines = []
        for line in lines:
            if line.startswith("API_CREDENTIALS="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                new_val = f"{val},{pair_str}" if val else pair_str
                new_lines.append(f"API_CREDENTIALS={new_val}")
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            new_lines.append(f"API_CREDENTIALS={pair_str}")

        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        LOGGER.info(
            "✨ Automatically registered new API Key %d to .env and runtime pool!",
            api_id,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Could not update .env with new API credential: %s", exc)


async def _create_api_on_my_telegram_org(
    client: TelegramClient,
    session_name: str,
    phone: str,
    session_http: aiohttp.ClientSession,
) -> tuple[int, str] | None:
    """Create or extract API_ID & API_HASH on my.telegram.org for an active session."""
    if not phone:
        return None

    phone_formatted = phone if phone.startswith("+") else f"+{phone}"

    try:
        # Step 1: Send password request to my.telegram.org
        async with session_http.post(
            "https://my.telegram.org/auth/send_password",
            data={"phone": phone_formatted},
            timeout=aiohttp.ClientTimeout(total=8),
        ) as res:
            if res.status != 200:
                return None
            data = await res.json()
            random_hash = data.get("random_hash")
            if not random_hash:
                return None

        # Step 2: Fetch web login code from Telegram channel 777000
        await asyncio.sleep(1.0)
        web_code = None
        start_t = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_t < 15:
            try:
                async for msg in client.iter_messages(777000, limit=5):
                    text = msg.text or ""
                    match = re.search(r"\b([a-zA-Z0-9_-]{8,14})\b", text)
                    if match:
                        web_code = match.group(1)
                        break
            except Exception:  # noqa: BLE001, S110
                pass
            if web_code:
                break
            await asyncio.sleep(1.5)

        if not web_code:
            return None

        # Step 3: Login to my.telegram.org
        async with session_http.post(
            "https://my.telegram.org/auth/login",
            data={
                "phone": phone_formatted,
                "random_hash": random_hash,
                "password": web_code,
            },
            timeout=aiohttp.ClientTimeout(total=8),
        ) as res:
            res_text = await res.text()
            if "true" not in res_text.lower() and res.status != 200:
                return None

        # Step 4: GET /apps page
        async with session_http.get(
            "https://my.telegram.org/apps",
            timeout=aiohttp.ClientTimeout(total=8),
        ) as res:
            html = await res.text()

        api_id_match = re.search(
            r"<strong>API id:</strong>\s*<span>(\d+)</span>", html
        ) or re.search(r'name="app_id"\s+value="(\d+)"', html)
        api_hash_match = re.search(
            r"<strong>API hash:</strong>\s*<span>([a-f0-9]{32})</span>", html
        ) or re.search(r'name="app_hash"\s+value="([a-f0-9]{32})"', html)

        if api_id_match and api_hash_match:
            api_id = int(api_id_match.group(1))
            api_hash = api_hash_match.group(1)
            _append_api_credential_to_env(api_id, api_hash)
            return api_id, api_hash

        # Step 5: Create new App
        form_hash_match = re.search(r'name="hash"\s+value="([^"]+)"', html)
        form_hash = form_hash_match.group(1) if form_hash_match else ""

        app_title = f"App_{session_name[:8]}"
        app_shortname = f"app_{session_name[:6]}"

        async with session_http.post(
            "https://my.telegram.org/apps/create",
            data={
                "hash": form_hash,
                "app_title": app_title,
                "app_shortname": app_shortname,
                "app_url": "",
                "app_platform": "desktop",
                "app_desc": "",
            },
            timeout=aiohttp.ClientTimeout(total=8),
        ) as res:
            create_html = await res.text()

        api_id_match = re.search(
            r"<strong>API id:</strong>\s*<span>(\d+)</span>", create_html
        ) or re.search(r'name="app_id"\s+value="(\d+)"', create_html)
        api_hash_match = re.search(
            r"<strong>API hash:</strong>\s*<span>([a-f0-9]{32})</span>", create_html
        ) or re.search(r'name="app_hash"\s+value="([a-f0-9]{32})"', create_html)

        if api_id_match and api_hash_match:
            api_id = int(api_id_match.group(1))
            api_hash = api_hash_match.group(1)
            _append_api_credential_to_env(api_id, api_hash)
            return api_id, api_hash

    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "Auto my.telegram.org API creation failed for %s: %s", session_name, exc
        )

    return None


_TG_REQUEST_LOCK = asyncio.Semaphore(15)


async def process_single_login_email(
    session_file: Path,
    credentials: list[tuple[int, str]],
    session_http: aiohttp.ClientSession,
    *,
    job_progress: JobProgress | None = None,
    max_flood_wait: int = 0,
    max_flood_retries: int = 1,
) -> LoginEmailDetail:
    """Inspect and update login email for a single session file."""
    session_name = session_file.stem
    phone = ""

    all_creds = list(credentials)
    for extra in _RUNTIME_EXTRA_CREDENTIALS:
        if extra not in all_creds:
            all_creds.append(extra)

    creds_shuffled = random.sample(all_creds, len(all_creds)) if all_creds else []
    last_flood_error = ""

    for api_id, api_hash in creds_shuffled:
        client = None
        old_pattern = None
        try:
            device_kwargs = get_stable_device_params(session_file)
            client = TelegramClient(
                str(session_file.with_suffix("")),
                api_id,
                api_hash,
                flood_sleep_threshold=0,
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

            # Create disposable temp email with automatic retry
            mail_tuple = None
            for _mail_attempt in range(3):
                mail_tuple = await _create_mail_tm_account(session_http)
                if mail_tuple:
                    break
                await asyncio.sleep(0.3)

            if not mail_tuple:
                return LoginEmailDetail(
                    session_name=session_name,
                    phone=phone,
                    status="error",
                    old_email_pattern=old_pattern,
                    message="Could not create disposable email",
                )

            new_email, mail_token, base_url = mail_tuple
            purpose = types.EmailVerifyPurposeLoginChange()

            # Request verification code from Telegram
            if job_progress and job_progress.cancel_requested:
                raise JobCancelled("Operation cancelled")
            try:
                async with _TG_REQUEST_LOCK:
                    await asyncio.sleep(0.05)
                    await asyncio.wait_for(
                        client(
                            functions.account.SendVerifyEmailCodeRequest(
                                purpose=purpose, email=new_email
                            )
                        ),
                        timeout=15,
                    )
            except FloodWaitError as exc:
                seconds = getattr(exc, "seconds", 0)
                last_flood_error = f"Telegram limit: Must wait {seconds}s required"
                LOGGER.info(
                    "FloodWait of %ds for %s on API key %s. Trying next API credential...",
                    seconds,
                    session_name,
                    api_id,
                )
                continue

            # Poll OTP code from email inbox
            otp_code = await _poll_mail_tm_otp(
                session_http, mail_token, timeout=25, base_url=base_url
            )
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
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Login email error for %s: %s", session_name, exc)
            continue
        finally:
            if client is not None:
                with suppress(Exception):
                    await client.disconnect()

    if last_flood_error:
        return LoginEmailDetail(
            session_name=session_name,
            phone=phone,
            status="error",
            old_email_pattern=old_pattern,
            message=last_flood_error,
        )

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
    max_concurrency: int = 30,
    original_name: str | None = None,
) -> LoginEmailBatchResult:
    """Process a batch zip archive or single session for login email management in parallel."""
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
            target = (
                tmp_dir
                / "sessions"
                / (Path(original_name).name if original_name else input_path.name)
            )
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

        semaphore = asyncio.Semaphore(max_concurrency)
        lock = asyncio.Lock()
        done_count = 0

        async def worker(sess_file: Path, session_http: aiohttp.ClientSession) -> None:
            nonlocal done_count
            async with semaphore:
                if job_progress.cancel_requested:
                    return

                detail = await process_single_login_email(
                    sess_file,
                    credentials,
                    session_http,
                    job_progress=job_progress,
                )

                async with lock:
                    if job_progress.cancel_requested:
                        return

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

                    done_count += 1
                    job_progress.done = done_count
                    job_progress.processed_accounts = done_count
                    if progress_callback:
                        with suppress(Exception):
                            res_p = progress_callback(job_progress)
                            if asyncio.iscoroutine(res_p):
                                await res_p

        async with aiohttp.ClientSession() as session_http:
            tasks = [
                asyncio.create_task(worker(sf, session_http)) for sf in session_files
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        if job_progress.cancel_requested:
            raise JobCancelled("Login email processing cancelled by user")

        # Build comprehensive report text file content
        report_header = [
            "================================================================================",
            "                   📧 CHANGE LOGIN EMAIL RESULTS REPORT                         ",
            "================================================================================",
            f"Total Accounts Processed: {result.total}",
            f"🟢 Email Updated:         {result.changed_count}",
            f"🟡 No Login Email:       {result.no_email_count}",
            f"❌ Failed / Limited:     {result.error_count}",
            "================================================================================",
            "",
        ]

        failed_details = [
            "--------------------------------------------------------------------------------",
            f"❌ FAILED / LIMITED ACCOUNTS DETAILS ({result.error_count})",
            "--------------------------------------------------------------------------------",
        ]
        no_email_details = [
            "--------------------------------------------------------------------------------",
            f"🟡 NO LOGIN EMAIL ACCOUNTS DETAILS ({result.no_email_count})",
            "--------------------------------------------------------------------------------",
        ]
        updated_details = [
            "--------------------------------------------------------------------------------",
            f"🟢 UPDATED ACCOUNTS DETAILS ({result.changed_count})",
            "--------------------------------------------------------------------------------",
        ]

        idx_f, idx_n, idx_u = 1, 1, 1
        for d in result.details:
            phone_str = f"+{d.phone}" if d.phone else "N/A"
            if d.status == "changed":
                updated_details.append(
                    f"{idx_u}. Session: {d.session_name}.session\n"
                    f"   • Status:  SUCCESS (Email Updated)\n"
                    f"   • Phone:   {phone_str}\n"
                    f"   • Email:   {d.new_email or 'N/A'}\n"
                    f"   • Note:    {d.message}\n"
                )
                idx_u += 1
            elif d.status == "no_email":
                no_email_details.append(
                    f"{idx_n}. Session: {d.session_name}.session\n"
                    f"   • Status:  SKIP (No Login Email Set)\n"
                    f"   • Phone:   {phone_str}\n"
                    f"   • Note:    {d.message}\n"
                )
                idx_n += 1
            else:
                failed_details.append(
                    f"{idx_f}. Session: {d.session_name}.session\n"
                    f"   • Status:  FAILED / LIMITED\n"
                    f"   • Phone:   {phone_str}\n"
                    f"   • Reason:  {d.message}\n"
                )
                idx_f += 1

        full_report_text = "\n".join(
            report_header
            + failed_details
            + [""]
            + no_email_details
            + [""]
            + updated_details
        )

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
                z.writestr("failure_reasons.txt", full_report_text)
                for f in failed_dir.glob("*.session"):
                    z.write(f, arcname=f.name)
            result.failed_session_zip = err_zip

        if result.total > 0:
            class_zip = output_dir / f"Login_Email_Classified_{token}.zip"
            with zipfile.ZipFile(class_zip, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("report.txt", full_report_text)
                for root, _, files in shutil.os.walk(classified_dir):
                    for file_name in files:
                        full_path = Path(root) / file_name
                        rel_path = full_path.relative_to(classified_dir)
                        z.write(full_path, arcname=str(rel_path))
            result.classified_zip = class_zip

    return result
