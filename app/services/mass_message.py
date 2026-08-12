from __future__ import annotations

import asyncio
import csv
import json
import logging
import shutil
import tempfile
import time
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Job
from app.services.file_merge import (
    _is_valid_sqlite_session,
    extract_account_identifier,
)
from app.services.session_to_tdata import _ensure_opentele_patched

LOGGER = logging.getLogger(__name__)


@dataclass
class Recipient:
    raw_identifier: str
    recipient_type: str  # 'username' | 'id' | 'phone'
    user_id: int | None = None
    username: str | None = None
    phone: str | None = None


@dataclass
class MassMessageResult:
    total: int
    sent: int
    failed: int
    skipped: int
    details: list[dict[str, Any]] = field(default_factory=list)
    report_path: Path | None = None


import zipfile


def parse_recipients_from_file(file_path: Path) -> list[Recipient]:
    """Parse TXT, CSV, or ZIP archive containing recipient lists and deduplicate."""
    recipients: list[Recipient] = []
    seen: set[str] = set()

    suffix = file_path.suffix.lower()
    text_contents: list[str] = []

    if suffix == ".zip":
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                for name in zf.namelist():
                    if name.lower().endswith((".txt", ".csv")):
                        with zf.open(name) as f:
                            raw = f.read()
                            text_contents.append(raw.decode("utf-8", errors="ignore"))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Could not read ZIP recipient archive %s: %s", file_path, exc)
            return []
    else:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            text_contents.append(content)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Could not read recipient file: %s", exc)
            return []

    for content in text_contents:
        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = [p.strip() for p in line.split(",") if p.strip()]
            for target in parts:
                clean = target.strip()
                if not clean or clean in seen:
                    continue

                seen.add(clean)

                if clean.startswith("@"):
                    recipients.append(
                        Recipient(
                            raw_identifier=clean,
                            recipient_type="username",
                            username=clean.lstrip("@"),
                        )
                    )
                elif clean.startswith("+") or (
                    clean.isdigit() and len(clean) >= 10 and not clean.startswith("8")
                ):
                    recipients.append(
                        Recipient(
                            raw_identifier=clean,
                            recipient_type="phone",
                            phone=clean if clean.startswith("+") else f"+{clean}",
                        )
                    )
                elif clean.isdigit():
                    recipients.append(
                        Recipient(
                            raw_identifier=clean,
                            recipient_type="id",
                            user_id=int(clean),
                        )
                    )
                else:
                    uname = clean.lstrip("@")
                    recipients.append(
                        Recipient(
                            raw_identifier=clean,
                            recipient_type="username",
                            username=uname,
                        )
                    )

    return recipients


def generate_mass_message_report(
    details: Sequence[dict[str, Any]], output_path: Path, format_type: str = "txt"
) -> Path:
    """Generate a downloadable summary report in TXT or CSV format."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format_type.lower() == "csv":
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Recipient", "Status", "Session", "Error/Details"])
            for d in details:
                writer.writerow(
                    [
                        d.get("recipient", ""),
                        d.get("status", ""),
                        d.get("session", ""),
                        d.get("details", ""),
                    ]
                )
    else:
        lines = [
            "==========================================",
            "      MASS MESSAGE EXECUTION REPORT       ",
            "==========================================",
            "",
            f"Total Processed: {len(details)}",
            "",
            "DETAILS:",
            "------------------------------------------",
        ]
        for d in details:
            lines.append(
                f"[{d.get('status', 'UNKNOWN')}] {d.get('recipient', '')} | Session: {d.get('session', '')} | Details: {d.get('details', 'OK')}"
            )
        lines.append("------------------------------------------")
        output_path.write_text("\n".join(lines), encoding="utf-8")

    return output_path


@dataclass
class SessionContactStat:
    session_name: str
    status: str  # 'ok' | 'no_contacts' | 'unauthorized' | 'invalid_sqlite' | 'error'
    contacts_found: int = 0
    error_detail: str | None = None


@dataclass
class ContactExtractionResult:
    recipients: list[Recipient]
    stats: list[SessionContactStat]


async def extract_contacts_from_sessions(
    session_files: Sequence[Path], credentials: list[tuple[int, str]]
) -> ContactExtractionResult:
    """Fetch contacts from uploaded sessions as recipients with detailed stats."""
    _ensure_opentele_patched()
    recipients: list[Recipient] = []
    seen: set[str] = set()
    stats: list[SessionContactStat] = []

    # Each session needs a connect + GetContactsRequest. Sequential fetching
    # made multi-session batches slow; a bounded semaphore parallelizes while
    # keeping the shared api_id / IP flood-safe. The starting credential pair
    # is staggered round-robin so sessions do not all pile onto api_id #0.
    fetch_semaphore = asyncio.Semaphore(
        min(_CONTACTS_FETCH_CONCURRENCY, len(session_files) or 1)
    )

    async def fetch_one(index: int) -> tuple[SessionContactStat, list[Recipient]]:
        sess_file = session_files[index]
        if not _is_valid_sqlite_session(sess_file):
            return (
                SessionContactStat(
                    session_name=sess_file.name,
                    status="invalid_sqlite",
                    contacts_found=0,
                    error_detail="Invalid SQLite database structure or missing auth_key",
                ),
                [],
            )

        async with fetch_semaphore:
            last_err: str | None = None
            session_recipients: list[Recipient] = []

            if credentials:
                start = index % len(credentials)
                creds = credentials[start:] + credentials[:start]
            else:
                creds = credentials

            for api_id, api_hash in creds:
                try:
                    from telethon import (  # type: ignore[import-untyped]
                        TelegramClient,
                        functions,
                    )
                except ModuleNotFoundError:
                    last_err = "Telethon not installed"
                    break

                with tempfile.TemporaryDirectory(prefix="ftgc_contacts_fetch_") as tmp:
                    run_sess = Path(tmp) / "acc.session"
                    shutil.copy2(sess_file, run_sess)
                    from app.services.device_params import get_stable_device_params
                    device_kwargs = get_stable_device_params(sess_file)
                    client = TelegramClient(
                        str(run_sess.with_suffix("")),
                        api_id,
                        api_hash,
                        receive_updates=False,
                        **device_kwargs,
                    )
                    try:
                        await client.connect()
                        if not await client.is_user_authorized():
                            # Dead auth key: unauthorized under any api_id, so
                            # stop rotating through the credential list.
                            last_err = "Session unauthorized or revoked"
                            break

                        contacts_res = await client(
                            functions.contacts.GetContactsRequest(hash=0)
                        )
                        users = getattr(contacts_res, "users", [])
                        found_count = len(users)

                        for u in users:
                            uid = getattr(u, "id", None)
                            uname = getattr(u, "username", None)
                            phone = getattr(u, "phone", None)

                            if uname:
                                session_recipients.append(
                                    Recipient(
                                        raw_identifier=f"@{uname}",
                                        recipient_type="username",
                                        username=uname,
                                        user_id=uid,
                                    )
                                )
                            elif uid:
                                session_recipients.append(
                                    Recipient(
                                        raw_identifier=str(uid),
                                        recipient_type="id",
                                        user_id=uid,
                                    )
                                )
                            elif phone:
                                session_recipients.append(
                                    Recipient(
                                        raw_identifier=f"+{phone}",
                                        recipient_type="phone",
                                        phone=f"+{phone}",
                                    )
                                )

                        if found_count > 0:
                            return (
                                SessionContactStat(
                                    session_name=sess_file.name,
                                    status="ok",
                                    contacts_found=found_count,
                                ),
                                session_recipients,
                            )
                        return (
                            SessionContactStat(
                                session_name=sess_file.name,
                                status="no_contacts",
                                contacts_found=0,
                                error_detail="Account has 0 saved Telegram contacts",
                            ),
                            session_recipients,
                        )
                    except Exception as exc:  # noqa: BLE001
                        last_err = str(exc)
                        LOGGER.debug(
                            "Contacts fetch failed for session %s: %s",
                            sess_file.name,
                            exc,
                        )
                    finally:
                        with suppress(Exception):
                            await client.disconnect()

            return (
                SessionContactStat(
                    session_name=sess_file.name,
                    status="unauthorized"
                    if last_err and "unauthorized" in last_err
                    else "error",
                    contacts_found=0,
                    error_detail=last_err or "Connection failed",
                ),
                session_recipients,
            )

    fetched = await asyncio.gather(
        *(fetch_one(index) for index in range(len(session_files)))
    )

    LOGGER.info("Starting Contact Extraction from %d session(s)...", len(session_files))

    for stat, session_recipients in fetched:
        # Global dedupe in session order keeps recipients deterministic.
        for r in session_recipients:
            key = str(r.user_id or r.username or r.phone)
            if not key or key in seen:
                continue
            seen.add(key)
            recipients.append(r)
        stats.append(stat)

        if stat.status == "ok":
            LOGGER.info(
                "Extract Contacts: Session=%s | Status=SUCCESS | ContactsFound=%d",
                stat.session_name,
                stat.contacts_found,
            )
        else:
            LOGGER.warning(
                "Extract Contacts: Session=%s | Status=%s | Reason=%s",
                stat.session_name,
                stat.status,
                stat.error_detail or "N/A",
            )

    LOGGER.info(
        "Extract Contacts Summary: Total Sessions=%d | Unique Recipients Extracted=%d",
        len(session_files),
        len(recipients),
    )

    return ContactExtractionResult(recipients=recipients, stats=stats)


async def send_mass_message_to_recipient(
    client: Any,
    recipient: Recipient,
    text: str,
    media_path: Path | None = None,
    entity_cache: dict[str, Any] | None = None,
    max_retries: int = 2,
) -> tuple[str, str]:
    """Real Telethon sending layer for a single recipient with caching & retry."""
    try:
        from telethon.errors import (  # type: ignore[import-untyped]
            AuthKeyUnregisteredError,
            FloodWaitError,
            InputUserDeactivatedError,
            PeerFloodError,
            RPCError,
            UserDeactivatedBanError,
            UserDeactivatedError,
            UserIsBlockedError,
            UserPrivacyRestrictedError,
        )
    except ModuleNotFoundError:
        return "FAILED", "TelethonNotInstalled"

    cache_key = str(
        recipient.user_id
        or recipient.username
        or recipient.phone
        or recipient.raw_identifier
    )
    entity: Any = None

    if entity_cache is not None and cache_key in entity_cache:
        entity = entity_cache[cache_key]

    if entity is None:
        target: Any = recipient.raw_identifier
        if recipient.user_id:
            target = recipient.user_id
        elif recipient.username:
            target = recipient.username
        elif recipient.phone:
            target = recipient.phone

        try:
            entity = await client.get_input_entity(target)
            if entity_cache is not None:
                entity_cache[cache_key] = entity
        except Exception:  # noqa: BLE001
            entity = target

    attempt = 0
    while True:
        try:
            if media_path and media_path.exists():
                await client.send_file(entity, str(media_path), caption=text or None)
            else:
                await client.send_message(entity, text)

            return "SENT", "Success"

        except FloodWaitError as exc:
            LOGGER.warning(
                "FloodWait for recipient %s: %s seconds",
                recipient.raw_identifier,
                getattr(exc, "seconds", 0),
            )
            return "SKIPPED", f"FloodWait {getattr(exc, 'seconds', 0)}s"
        except PeerFloodError:
            LOGGER.warning("PeerFlood error for recipient %s", recipient.raw_identifier)
            return "SKIPPED", "PeerFlood"
        except UserPrivacyRestrictedError:
            return "FAILED", "UserPrivacyRestricted"
        except (
            UserIsBlockedError,
            UserDeactivatedError,
            UserDeactivatedBanError,
            InputUserDeactivatedError,
        ):
            return "FAILED", "UserBlockedOrDeactivated"
        except AuthKeyUnregisteredError:
            return "SKIPPED", "SessionRevoked"
        except (ValueError, TypeError) as exc:
            return "FAILED", f"InvalidRecipient: {exc}"
        except RPCError as exc:
            if attempt < max_retries:
                attempt += 1
                await asyncio.sleep(1.0 * attempt)
                continue
            LOGGER.warning(
                "RPC error for %s after retries: %s", recipient.raw_identifier, exc
            )
            return "FAILED", f"RPCError: {exc}"
        except Exception as exc:  # noqa: BLE001
            if attempt < max_retries:
                attempt += 1
                await asyncio.sleep(1.0 * attempt)
                continue
            LOGGER.warning(
                "Send message failed for %s: %s", recipient.raw_identifier, exc
            )
            return "FAILED", str(exc)


class ProcessRateLimiter:
    """Limits message dispatch rate within the local process workers using a token-bucket interval."""

    def __init__(self, min_interval_seconds: float = 0.1) -> None:
        self.min_interval = min_interval_seconds
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_call = time.time()


# Alias for backward compatibility
GlobalRateLimiter = ProcessRateLimiter

# Max concurrent contact fetches / client bootstraps. All sessions share the
# global api_credential pairs (one IP / api_id), so the ceiling stays low.
_CONTACTS_FETCH_CONCURRENCY = 8
_BOOTSTRAP_CONCURRENCY = 8


def format_mass_message_summary(
    job_id: str,
    accounts_count: int,
    total_recipients: int,
    sent: int,
    failed: int,
    skipped: int,
    duration_seconds: float,
    language: str = "en",
    status: str = "completed",
    last_error_session: str | None = None,
    last_error_detail: str | None = None,
) -> str:
    """Format final completion summary message with statistics."""
    minutes = int(duration_seconds // 60)
    seconds = int(duration_seconds % 60)
    duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

    speed = (sent / (duration_seconds / 60)) if duration_seconds > 0 else 0.0
    speed_str = f"{speed:.1f} msg/min"

    job_ref = job_id if job_id.startswith("MM-") else job_id[:8].upper()

    title = ""
    footer = ""

    if status == "paused":
        reason_heading = {
            "bn": "স্থগিতের কারণ",
            "hi": "रोकने का कारण",
            "ur": "روکنے کی وجہ",
            "ar": "سبب التعليق",
            "zh": "暂停原因",
            "en": "Pause Cause",
        }
    else:
        reason_heading = {
            "bn": "এড়িয়ে যাওয়া/ব্যর্থতার কারণ",
            "hi": "छोड़े गए/विफल होने का कारण",
            "ur": "چھوڑنے/ناکامی کی وجہ",
            "ar": "سبب التخطي/الفشل",
            "zh": "跳过/失败原因",
            "en": "Skip / Fail Cause",
        }
    field_labels = {
        "bn": ("সেশন", "বিবরণ"),
        "hi": ("सत्र", "विवरण"),
        "ur": ("سیشن", "تفصیل"),
        "ar": ("الجلسة", "التفاصيل"),
        "zh": ("会话", "详情"),
        "en": ("Session", "Detail"),
    }

    reason_block = ""
    if last_error_session or last_error_detail:
        lang = language if language in reason_heading else "en"
        heading = reason_heading[lang]
        sess_label, detail_label = field_labels[lang]
        reason_block = f"\n\n⚠️ **{heading}:**"
        if last_error_session:
            reason_block += f"\n🔑 **{sess_label}:** `{last_error_session}`"
        if last_error_detail:
            reason_block += f"\n❌ **{detail_label}:** `{last_error_detail}`"

    if status == "paused":
        if language == "bn":
            title = f"⚠️ **গণ বার্তার কাজ স্থগিত করা হয়েছে (Job #{job_ref})**\n\n"
            footer = f"{reason_block}\n\n⚠️ *রেট লিমিট বা সেশন শেষ হওয়ার কারণে কাজটি স্থগিত করা হয়েছে। আপনি যেকোনো সময় এটি পুনরায় শুরু করতে পারেন।*"
        elif language == "hi":
            title = f"⚠️ **सामूहिक संदेश कार्य रोक दिया गया है (Job #{job_ref})**\n\n"
            footer = f"{reason_block}\n\n⚠️ *दर सीमा या सत्र समाप्ति के कारण कार्य रोक दिया गया है। आप इसे कभी भी फिर से शुरू कर सकते हैं।*"
        elif language == "ur":
            title = f"⚠️ **ماس میسج کام روک دیا گیا ہے (Job #{job_ref})**\n\n"
            footer = f"{reason_block}\n\n⚠️ *ریٹ لمیٹ یا سیشن ختم ہونے کی وجہ سے کام روک دیا گیا ہے۔ آپ اسے کسی بھی وقت دوبارہ شروع کر سکتے ہیں۔*"
        elif language == "ar":
            title = f"⚠️ **تم تعليق مهمة الرسائل الجماعية (Job #{job_ref})**\n\n"
            footer = f"{reason_block}\n\n⚠️ *تم تعليق المهمة بسبب قيود المعدل أو نفاد الجلسات. يمكنك استئنافها في أي وقت.*"
        elif language == "zh":
            title = f"⚠️ **群发消息任务已暂停 (Job #{job_ref})**\n\n"
            footer = f"{reason_block}\n\n⚠️ *由于速率限制或会话耗尽，任务已暂停。您可以随时恢复。*"
        else:
            title = f"⚠️ **Mass Message Job Paused (Job #{job_ref})**\n\n"
            footer = f"{reason_block}\n\n⚠️ *Job paused due to rate limiting or session exhaustion. You can resume it anytime.*"
    elif status == "stopped":
        if language == "bn":
            title = f"⛔ **গণ বার্তার কাজ বন্ধ করা হয়েছে (Job #{job_ref})**\n\n"
        elif language == "hi":
            title = f"⛔ **सामूहिक संदेश कार्य बंद कर दिया गया है (Job #{job_ref})**\n\n"
        elif language == "ur":
            title = f"⛔ **ماس میسج کام بند کر دیا گیا ہے (Job #{job_ref})**\n\n"
        elif language == "ar":
            title = f"⛔ **تم إيقاف مهمة الرسائل الجماعية (Job #{job_ref})**\n\n"
        elif language == "zh":
            title = f"⛔ **群发消息任务已停止 (Job #{job_ref})**\n\n"
        else:
            title = f"⛔ **Mass Message Job Stopped (Job #{job_ref})**\n\n"
    else:
        if language == "bn":
            title = f"📊 **গণ বার্তার সারাংশ রিপোর্ট (Job #{job_ref})**\n\n"
        elif language == "hi":
            title = f"📊 **सामूहिक संदेश सारांश रिपोर्ट (Job #{job_ref})**\n\n"
        elif language == "ur":
            title = f"📊 **ماس میسج خلاصہ رپورٹ (Job #{job_ref})**\n\n"
        elif language == "ar":
            title = f"📊 **تقرير ملخص الرسائل الجماعية (Job #{job_ref})**\n\n"
        elif language == "zh":
            title = f"📊 **群发消息摘要报告 (Job #{job_ref})**\n\n"
        else:
            title = f"📊 **Mass Message Completion Summary (Job #{job_ref})**\n\n"

    if language == "bn":
        body = (
            f"🆔 জব আইডি: `#{job_ref}`\n"
            f"👤 সক্রিয় অ্যাকাউন্ট: {accounts_count}\n"
            f"👥 মোট প্রাপক: {total_recipients}\n\n"
            f"✅ পাঠানো হয়েছে: {sent}\n"
            f"❌ ব্যর্থ: {failed}\n"
            f"⏭ এড়িয়ে গেছে: {skipped}\n\n"
            f"⏱ সময়কাল: {duration_str}\n"
            f"⚡ গড় গতি: {speed_str}"
        )
    elif language == "hi":
        body = (
            f"🆔 जॉब आईडी: `#{job_ref}`\n"
            f"👤 सक्रिय खाते: {accounts_count}\n"
            f"👥 कुल प्राप्तकर्ता: {total_recipients}\n\n"
            f"✅ भेजा गया: {sent}\n"
            f"❌ विफल: {failed}\n"
            f"⏭ छोड़ दिया: {skipped}\n\n"
            f"⏱ अवधि: {duration_str}\n"
            f"⚡ औसत गति: {speed_str}"
        )
    elif language == "ur":
        body = (
            f"🆔 جاب آئی ڈی: `#{job_ref}`\n"
            f"👤 فعال اکاؤنٹس: {accounts_count}\n"
            f"👥 کل وصول کنندگان: {total_recipients}\n\n"
            f"✅ بھیج دیا: {sent}\n"
            f"❌ ناکام: {failed}\n"
            f"⏭ چھوڑ دیا: {skipped}\n\n"
            f"⏱ دورانیہ: {duration_str}\n"
            f"⚡ اوسط رفتار: {speed_str}"
        )
    elif language == "ar":
        body = (
            f"🆔 معرف المهمة: `#{job_ref}`\n"
            f"👤 الحسابات النشطة: {accounts_count}\n"
            f"👥 إجمالي المستلمين: {total_recipients}\n\n"
            f"✅ تم الإرسال: {sent}\n"
            f"❌ فشل: {failed}\n"
            f"⏭ تم التخطي: {skipped}\n\n"
            f"⏱ المدة: {duration_str}\n"
            f"⚡ متوسط السرعة: {speed_str}"
        )
    elif language == "zh":
        body = (
            f"🆔 任务 ID: `#{job_ref}`\n"
            f"👤 活跃账户: {accounts_count}\n"
            f"👥 总接收者: {total_recipients}\n\n"
            f"✅ 已发送: {sent}\n"
            f"❌ 失败: {failed}\n"
            f"⏭ 已跳过: {skipped}\n\n"
            f"⏱ 耗时: {duration_str}\n"
            f"⚡ 平均速度: {speed_str}"
        )
    else:
        body = (
            f"🆔 Job ID: `#{job_ref}`\n"
            f"👤 Active Accounts: {accounts_count}\n"
            f"👥 Total Recipients: {total_recipients}\n\n"
            f"✅ Sent: {sent}\n"
            f"❌ Failed: {failed}\n"
            f"⏭ Skipped: {skipped}\n\n"
            f"⏱ Duration: {duration_str}\n"
            f"⚡ Average Speed: {speed_str}"
        )

    if status != "paused":
        footer = reason_block

    return f"{title}{body}{footer}"


async def create_telethon_client_for_session(
    sess_file: Path, api_credentials: list[tuple[int, str]]
) -> tuple[Any, Path | None, tempfile.TemporaryDirectory[str] | None]:
    """Create and connect TelethonClient for a session file."""
    _ensure_opentele_patched()
    try:
        from telethon import TelegramClient  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return None, None, None

    if not _is_valid_sqlite_session(sess_file):
        return None, None, None

    for api_id, api_hash in api_credentials:
        tmp = tempfile.TemporaryDirectory(prefix="ftgc_mass_run_")
        run_sess = Path(tmp.name) / "account.session"
        shutil.copy2(sess_file, run_sess)

        from app.services.device_params import get_stable_device_params
        device_kwargs = get_stable_device_params(sess_file)
        client = TelegramClient(
            str(run_sess.with_suffix("")), api_id, api_hash, receive_updates=False, **device_kwargs
        )
        try:
            await client.connect()
            if await client.is_user_authorized():
                return client, run_sess, tmp
            await client.disconnect()
            tmp.cleanup()
        except Exception:  # noqa: BLE001
            with suppress(Exception):
                await client.disconnect()
            tmp.cleanup()

    return None, None, None


def recover_interrupted_mass_message_jobs(
    session_factory: sessionmaker[Session],
) -> list[dict[str, Any]]:
    """Load interrupted mass-message jobs after a crash or restart, transition running jobs to paused,
    and reconstruct pending recipients to guarantee zero duplicate sends.
    """
    recovered_jobs: list[dict[str, Any]] = []
    with session_factory() as db_sess:
        interrupted = (
            db_sess.query(Job)
            .filter(
                Job.operation == "mass_message",
                Job.status.in_(["running", "paused"]),
            )
            .all()
        )
        for job in interrupted:
            options = json.loads(job.options_json or "{}")
            pending = options.get("pending_recipients", [])
            completed = options.get("completed_recipients", [])

            # Deduplicate pending list against completed list to guarantee zero duplicate sends
            unique_pending = [r for r in pending if r not in completed]
            options["pending_recipients"] = unique_pending

            # Reset status to paused so user can safely review and hit Resume
            job.status = "paused"
            job.options_json = json.dumps(options)

            recovered_jobs.append(
                {
                    "job_id": job.id,
                    "display_id": options.get("display_id", job.id[:8]),
                    "user_id": job.user_id,
                    "pending_count": len(unique_pending),
                    "total_count": options.get("total", 0),
                }
            )
        db_sess.commit()
    return recovered_jobs


async def resume_mass_message_job(
    job_id: str,
    session_factory: sessionmaker[Session],
    api_credentials: list[tuple[int, str]],
    bot: Any | None = None,
) -> MassMessageResult:
    """Operational recovery execution layer:
    Reconstructs an interrupted job from DB state, reconnects session clients,
    restores recipient queue, launches workers, and processes all remaining recipients.

    Note on At-Least-Once Delivery:
    Because Telegram API RPC calls lack native idempotency tokens across connection resets,
    the brief window between Telegram delivery and database checkpoint commitment means
    messaging delivery operates with At-Least-Once guarantees under unexpected crash conditions.
    """
    with session_factory() as db_sess:
        job = db_sess.query(Job).filter(Job.id == job_id).first()
        if not job or job.operation != "mass_message":
            raise ValueError(f"Job {job_id} not found or invalid operation.")

        job.status = "running"
        options = json.loads(job.options_json or "{}")

    display_id = options.get("display_id", job_id[:8])
    LOGGER.info("Resuming mass message job %s (%s)", job_id, display_id)
    message_text = options.get("message_text", "")
    media_file_id = options.get("media_file_id")
    session_files = [
        Path(p) for p in options.get("session_files", []) if Path(p).exists()
    ]
    pending_raw = options.get("pending_recipients", [])
    completed_raw = set(options.get("completed_recipients", []))

    # Deduplicate pending list against completed list
    remaining_identifiers = [r for r in pending_raw if r not in completed_raw]
    recipients = [
        Recipient(
            raw_identifier=r,
            recipient_type="username"
            if r.startswith("@")
            else ("phone" if r.startswith("+") else "id"),
            username=r.lstrip("@") if r.startswith("@") else None,
            phone=r if r.startswith("+") else None,
            user_id=int(r) if r.isdigit() else None,
        )
        for r in remaining_identifiers
    ]

    total = options.get("total", len(completed_raw) + len(recipients))
    sent = options.get("sent", 0)
    failed = options.get("failed", 0)
    skipped = options.get("skipped", 0)
    details: list[dict[str, Any]] = options.get("details", [])

    media_file_path: Path | None = None
    if media_file_id and bot:
        file_info = await bot.get_file(media_file_id)
        if file_info and file_info.file_path:
            media_file_path = (
                Path(tempfile.gettempdir()) / f"mass_media_res_{uuid4().hex[:6]}"
            )
            await bot.download_file(
                file_info.file_path, destination=media_file_path, timeout=180
            )

    clients: list[tuple[Any, Path, tempfile.TemporaryDirectory[str]]] = []

    # Client bootstrap is a connect + authorize check per session. Sequential
    # bootstrap made resumes with many sessions slow (N×M connects worst
    # case); a bounded semaphore keeps the shared api_id / IP flood-safe.
    bootstrap_semaphore = asyncio.Semaphore(
        min(_BOOTSTRAP_CONCURRENCY, len(session_files) or 1)
    )

    async def bootstrap_one(
        sf: Path,
    ) -> tuple[Any, Path, tempfile.TemporaryDirectory[str]] | None:
        async with bootstrap_semaphore:
            cli, run_sess, tmp = await create_telethon_client_for_session(
                sf, api_credentials
            )
            if cli and run_sess and tmp:
                return cli, sf, tmp
        return None

    bootstrapped = await asyncio.gather(*(bootstrap_one(sf) for sf in session_files))
    clients = [entry for entry in bootstrapped if entry is not None]

    if not clients:
        for rec in recipients:
            failed += 1
            details.append(
                {
                    "recipient": rec.raw_identifier,
                    "session": "None",
                    "status": "FAILED",
                    "details": "UnauthorizedOrInvalidSessionOnResume",
                }
            )
    else:
        queue: asyncio.Queue[Recipient] = asyncio.Queue()
        for rec in recipients:
            queue.put_nowait(rec)

        lock = asyncio.Lock()
        limiter = ProcessRateLimiter(min_interval_seconds=0.1)

        async def worker(cli: Any, session_path: Path) -> None:
            nonlocal sent, failed, skipped
            entity_cache: dict[str, Any] = {}
            flood_until = 0.0

            while not queue.empty():
                now = time.time()
                if now < flood_until:
                    await asyncio.sleep(min(flood_until - now, 2.0))
                    continue

                try:
                    rec = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                await limiter.acquire()
                st, detail = await send_mass_message_to_recipient(
                    cli, rec, message_text, media_file_path, entity_cache=entity_cache
                )

                is_disabled = False
                if st == "SKIPPED":
                    if "FloodWait" in detail:
                        try:
                            sec_str = (
                                detail.replace("FloodWait", "")
                                .replace("s", "")
                                .strip()
                            )
                            sec = float(sec_str)
                            flood_until = time.time() + sec
                        except Exception:  # noqa: BLE001
                            flood_until = time.time() + 60.0
                    elif detail in ("PeerFlood", "SessionRevoked"):
                        is_disabled = True

                async with lock:
                    if st == "SENT":
                        sent += 1
                        LOGGER.info(
                            "Mass Message: Session=%s | Target=%s → SENT",
                            session_path.name,
                            rec.raw_identifier,
                        )
                    elif st == "SKIPPED":
                        skipped += 1
                        LOGGER.warning(
                            "Mass Message: Session=%s | Target=%s → SKIPPED (%s)",
                            session_path.name,
                            rec.raw_identifier,
                            detail,
                        )
                    else:
                        failed += 1
                        LOGGER.warning(
                            "Mass Message: Session=%s | Target=%s → FAILED (%s)",
                            session_path.name,
                            rec.raw_identifier,
                            detail,
                        )

                    details.append(
                        {
                            "recipient": rec.raw_identifier,
                            "session": session_path.name,
                            "status": st,
                            "details": detail,
                        }
                    )

                    # Checkpoint DB State
                    with session_factory() as db_sess:
                        j_ref = db_sess.query(Job).filter(Job.id == job_id).first()
                        if j_ref:
                            processed_cnt = sent + failed + skipped
                            j_ref.progress = (
                                int((processed_cnt / total) * 100) if total > 0 else 100
                            )
                            opt_snapshot = json.loads(j_ref.options_json or "{}")
                            completed_set = {d["recipient"] for d in details}
                            opt_snapshot.update(
                                {
                                    "sent": sent,
                                    "failed": failed,
                                    "skipped": skipped,
                                    "pending_recipients": [
                                        r.raw_identifier
                                        for r in recipients
                                        if r.raw_identifier
                                        not in completed_set
                                    ],
                                    "completed_recipients": list(completed_set),
                                }
                            )
                            j_ref.options_json = json.dumps(opt_snapshot)
                            db_sess.commit()

                queue.task_done()
                if is_disabled:
                    LOGGER.warning(
                        "Disabling session %s due to %s", session_path.name, detail
                    )
                    break

        worker_tasks = [asyncio.create_task(worker(cli, sf)) for cli, sf, _ in clients]
        await asyncio.gather(*worker_tasks, return_exceptions=True)

    # Cleanup clients and temp files
    for cli, _, tmp in clients:
        with suppress(Exception):
            await cli.disconnect()
        if tmp:
            with suppress(Exception):
                tmp.cleanup()

    if media_file_path and media_file_path.exists():
        media_file_path.unlink(missing_ok=True)

    processed_count = sent + failed + skipped
    is_interrupted = processed_count < total

    with session_factory() as db_sess:
        j_finish = db_sess.query(Job).filter(Job.id == job_id).first()
        if j_finish:
            if is_interrupted:
                j_finish.status = "paused"
                j_finish.progress = int((processed_count / total) * 100) if total > 0 else 0
                
                # Checkpoint DB State
                opt_snapshot = json.loads(j_finish.options_json or "{}")
                completed_set = {d["recipient"] for d in details}
                opt_snapshot.update(
                    {
                        "sent": sent,
                        "failed": failed,
                        "skipped": skipped,
                        "pending_recipients": [
                            r.raw_identifier
                            for r in recipients
                            if r.raw_identifier
                            not in completed_set
                        ],
                        "completed_recipients": list(completed_set),
                    }
                )
                j_finish.options_json = json.dumps(opt_snapshot)
            else:
                j_finish.status = "completed" if (sent > 0 or total == 0) else "failed"
                j_finish.progress = 100
            db_sess.commit()

    return MassMessageResult(
        total=total,
        sent=sent,
        failed=failed,
        skipped=skipped,
        details=details,
        report_path=None,
    )
