import asyncio
import bisect
import datetime
import logging
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aiogram import html

from app.services.contacts_checker import extract_zip_sessions_safe
from app.services.jobs import JobCancelled, JobProgress
from app.services.tdata_to_session import (
    _convert_tdata_dir_sync,
    extract_zip_tdata_safe,
    find_tdata_dirs,
)
from app.ui import EmojiRegistry

LOGGER = logging.getLogger(__name__)


class AccountAgeDatasetError(Exception):
    """Base exception for account age dataset issues."""


class DatasetNotFoundError(AccountAgeDatasetError):
    """Raised when dataset.json is missing."""


class DatasetCorruptError(AccountAgeDatasetError):
    """Raised when dataset.json is invalid or corrupted."""


DEFAULT_DATASET_PATH = Path(__file__).parent.parent / "data" / "dataset.json"

_CACHE_LOCK = threading.Lock()
_CACHED_MILESTONES: list[tuple[int, int, int, int]] | None = None
_CACHED_MILESTONE_IDS: list[int] | None = None
_CACHED_MTIME: float = 0.0

# The official "@Telegram" service chat. Telegram sends the very first
# message to every new account there, making its date equal to the
# day the account registered (most accurate registration signal).
_REGISTRATION_CHAT_ID = 777000

# Human-readable labels for the registration-time source methods.
SOURCE_LABELS = {
    "telegram_chat": "From @Telegram official chat (✅ Most accurate)",
    "saved_messages": "From Saved Messages (✅ Accurate)",
    "estimation": "Estimated based on user ID (⚠️ May be inaccurate, error could be months or years)",
}


def load_dataset_milestones(
    dataset_path: Path | str | None = None,
) -> tuple[list[tuple[int, int, int, int]], list[int]]:
    """Dynamically load and parse Telegram ID milestones from dataset.json.

    Thread-safe implementation protected by a threading.Lock.
    Returns (milestones, milestone_ids).

    Raises:
        DatasetNotFoundError: If dataset.json does not exist.
        DatasetCorruptError: If dataset.json cannot be parsed or contains invalid data.
    """
    global _CACHED_MILESTONES, _CACHED_MILESTONE_IDS, _CACHED_MTIME
    path = Path(dataset_path) if dataset_path else DEFAULT_DATASET_PATH
    if not path.exists():
        LOGGER.error("Dataset file not found at %s", path)
        raise DatasetNotFoundError(f"Dataset file not found at: {path}")

    mtime = path.stat().st_mtime

    with _CACHE_LOCK:
        if (
            _CACHED_MILESTONES is not None
            and _CACHED_MILESTONE_IDS is not None
            and mtime == _CACHED_MTIME
            and dataset_path is None
        ):
            return _CACHED_MILESTONES, _CACHED_MILESTONE_IDS

    try:
        import json

        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, list) or not raw_data:
            raise ValueError("Dataset JSON must be a non-empty list.")

        milestones = []
        seen_ids: set[int] = set()

        for item in raw_data:
            if not isinstance(item, dict) or "id" not in item or "date" not in item:
                raise ValueError("Dataset item missing 'id' or 'date' key.")
            uid = int(item["id"])
            if uid in seen_ids:
                raise ValueError(f"Duplicate Telegram ID found in dataset: {uid}")
            seen_ids.add(uid)

            parts = [int(p) for p in item["date"].split("-")]
            if len(parts) != 3:
                raise ValueError(f"Invalid date format in item: {item['date']}")

            try:
                # Validates actual calendar date (e.g. catches Feb 30th)
                _val_date = datetime.date(parts[0], parts[1], parts[2])
            except ValueError as date_err:
                raise ValueError(
                    f"Invalid calendar date '{item['date']}': {date_err}"
                ) from date_err

            milestones.append((uid, parts[0], parts[1], parts[2]))

        milestones.sort(key=lambda x: x[0])

        # Validate strictly increasing IDs after sorting
        for i in range(len(milestones) - 1):
            uid1 = milestones[i][0]
            uid2 = milestones[i + 1][0]
            if uid1 >= uid2:
                raise ValueError(f"IDs not strictly increasing: {uid1} >= {uid2}")

        milestone_ids = [m[0] for m in milestones]

        if dataset_path is None:
            with _CACHE_LOCK:
                _CACHED_MILESTONES = milestones
                _CACHED_MILESTONE_IDS = milestone_ids
                _CACHED_MTIME = mtime

        return milestones, milestone_ids
    except (DatasetNotFoundError, DatasetCorruptError):
        raise
    except Exception as err:
        LOGGER.error("Failed to parse dataset milestone file at %s: %s", path, err)
        raise DatasetCorruptError(f"Corrupt dataset file at {path}: {err}") from err


_MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def estimate_account_creation(
    user_id: int, dataset_path: Path | str | None = None
) -> tuple[int, int, str]:
    """Estimate registration year, month, and formatted age description from Telegram user_id.

    Interpolates linearly between milestone points found via bisect binary search on dataset.json.
    For IDs exceeding dataset bounds, returns a broad estimate with Low Confidence instead of unreliable day extrapolation.
    """
    milestones, milestone_ids = load_dataset_milestones(dataset_path)

    if user_id <= 0:
        return 2013, 8, "~ 14/8/2013\nEstimated August 2013"
    min_milestone = milestones[0]
    max_milestone = milestones[-1]

    # Handle User IDs exceeding the verified public community dataset limit
    if user_id > max_milestone[0]:
        _max_id, max_y, max_m, max_d = max_milestone
        full_month = _MONTH_NAMES[max_m - 1]
        max_date_str = f"{max_d} {_MONTH_NAMES[max_m - 1][:3]} {max_y}"
        created_str = (
            f"> {max_d}/{max_m}/{max_y}\n"
            f"Estimated after {full_month} {max_y} (Confidence: Low)\n"
            f"⚠️ <i>Note: User ID exceeds verified public community dataset limit ({max_date_str}).</i>"
        )
        return max_y, max_m, created_str

    # Handle User IDs below min milestone
    if user_id < min_milestone[0]:
        _min_id, min_y, min_m, min_d = min_milestone
        full_month = _MONTH_NAMES[min_m - 1]
        created_str = (
            f"< {min_d}/{min_m}/{min_y}\n"
            f"Estimated before {full_month} {min_y} (Confidence: Low)"
        )
        return min_y, min_m, created_str

    # Fast O(log N) bisect binary search for interpolation interval
    idx = bisect.bisect_right(milestone_ids, user_id)
    if idx > 0 and milestone_ids[idx - 1] == user_id:
        p1 = p2 = milestones[idx - 1]
    else:
        p1 = milestones[idx - 1]
        p2 = milestones[idx]

    id1, y1, m1, d1 = p1
    id2, y2, m2, d2 = p2

    date1 = datetime.date(y1, m1, d1)
    date2 = datetime.date(y2, m2, d2)

    if id2 == id1:
        est_date = date1
    else:
        ratio = (user_id - id1) / (id2 - id1)
        total_days = (date2 - date1).days
        est_date = date1 + datetime.timedelta(days=int(ratio * total_days))

    now = datetime.datetime.now(datetime.UTC).date()
    months_diff = max(0, (now.year - est_date.year) * 12 + (now.month - est_date.month))

    full_month = _MONTH_NAMES[est_date.month - 1]

    if months_diff < 1:
        rel_str = "newer than 1 month"
    elif months_diff < 12:
        rel_str = f"{months_diff} month{'s' if months_diff > 1 else ''} ago"
    else:
        years = months_diff // 12
        rel_str = f"{years} year{'s' if years > 1 else ''} old"

    created_str = (
        f"~ {est_date.day}/{est_date.month}/{est_date.year}\n"
        f"Estimated {est_date.day} {full_month[:3]} {est_date.year} ({rel_str})"
    )

    return est_date.year, est_date.month, created_str


DC_LOCATIONS: dict[int, str] = {
    1: "🇺🇸 DC1",
    2: "🇳🇱 DC2",
    3: "🇺🇸 DC3",
    4: "🇳🇱 DC4",
    5: "🇸🇬 DC5",
}


@dataclass(frozen=True)
class AccountAgeInfo:
    session_name: str
    user_id: int
    phone: str
    username: str
    first_name: str
    last_name: str
    is_premium: bool
    dc_id: int
    creation_estimate: str
    exact_creation_date: str | None = None
    is_scam: bool = False
    is_fake: bool = False
    is_verified: bool = False
    # New: how the registration time was resolved + extra metrics.
    registration_source: str = ""
    registration_common_groups: int = 0
    registration_error: str = ""

    @property
    def dc_name(self) -> str:
        return DC_LOCATIONS.get(self.dc_id, f"DC{self.dc_id}")

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.last_name]
        name = " ".join(p for p in parts if p).strip()
        return name if name else "N/A"

    @property
    def registration_date(self) -> str | None:
        """Exact YYYY-MM-DD registration date when a precise method hit."""
        return self.exact_creation_date


@dataclass(frozen=True)
class AccountAgeResult:
    total: int
    checked: int
    failed: int
    accounts: tuple[AccountAgeInfo, ...]
    failure_entries: tuple[tuple[str, str], ...] = ()
    report_path: Path | None = None
    classified_zip_path: Path | None = None
    failed_zip_path: Path | None = None

    @property
    def failures(self) -> tuple[tuple[str, str], ...]:
        return self.failure_entries


def _is_valid_session(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT auth_key FROM sessions LIMIT 1").fetchone()
        auth_key = bytes(row[0]) if row is not None and row[0] else b""
        return len(auth_key) == 256 and any(byte != 0 for byte in auth_key)
    except (OSError, sqlite3.DatabaseError):
        return False


async def _oldest_message_date(client: Any, entity: Any) -> datetime.datetime | None:
    """Date of the oldest message in a chat, or None (incl. on errors)."""
    try:
        messages = await client.get_messages(entity, limit=1, reverse=True)
        if messages and len(messages) > 0 and messages[0].date:
            return messages[0].date
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Oldest-message probe failed for %r: %s", entity, exc)
    return None


async def _resolve_registration(
    client: Any, user_id: int
) -> tuple[str | None, str, str]:
    """Best-effort registration date + human label.

    Methods by priority (as in the product spec):
      1. The date of Telegram's first message to the account in the
         official lib chat: exactly = registration day (most accurate).
      2. Saved Messages first entry (fairly accurate).
      3. Estimate from the user ID over the bundled dataset.
    Returns (date_str, source_key, human_label). date_str is None when no
    precise signal exists and estimation failed.
    """
    date = await _oldest_message_date(client, _REGISTRATION_CHAT_ID)
    if date is not None:
        return date.strftime("%Y-%m-%d"), "telegram_chat", SOURCE_LABELS["telegram_chat"]

    date = await _oldest_message_date(client, "me")
    if date is not None:
        return (
            date.strftime("%Y-%m-%d"),
            "saved_messages",
            SOURCE_LABELS["saved_messages"],
        )

    try:
        year, month, _ = estimate_account_creation(user_id)
        est = datetime.date(year, month, 1)
        return (
            est.strftime("%Y-%m-%d"),
            "estimation",
            SOURCE_LABELS["estimation"],
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Registration estimation failed for user %d: %s", user_id, exc)
        return None, "estimation", SOURCE_LABELS["estimation"]


async def fetch_single_account_age(
    session_path: Path,
    credentials: list[tuple[int, str]],
    proxy: tuple | None = None,
) -> AccountAgeInfo | None:
    """Resolve profile + registration time for one session file.

    Returns a full :class:`AccountAgeInfo` on success, or None when the
    session could not be authorized with any credential pair.
    """
    if not _is_valid_session(session_path):
        return None

    try:
        from telethon import TelegramClient  # type: ignore[import-untyped]
        from telethon.errors import RPCError  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return None

    for api_id, api_hash in credentials:
        with tempfile.TemporaryDirectory(prefix="ftgc_age_client_") as tmp_dir:
            run_session = Path(tmp_dir) / "account.session"
            shutil.copy2(session_path, run_session)
            from app.services.device_params import get_stable_device_params
            device_kwargs = get_stable_device_params(session_path)
            client = TelegramClient(
                str(run_session.with_suffix("")),
                api_id,
                api_hash,
                receive_updates=False,
                proxy=proxy,
                **device_kwargs,
            )
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    continue

                me = await client.get_me()
                if not me:
                    continue

                user_id = int(me.id)
                phone = getattr(me, "phone", "") or ""
                username = getattr(me, "username", "") or ""
                first_name = getattr(me, "first_name", "") or ""
                last_name = getattr(me, "last_name", "") or ""
                is_premium = bool(getattr(me, "premium", False))
                is_scam = bool(getattr(me, "scam", False))
                is_fake = bool(getattr(me, "fake", False))
                is_verified = bool(getattr(me, "verified", False))
                dc_id = getattr(client.session, "dc_id", 0) or 0

                _, _, estimate_str = estimate_account_creation(user_id)

                date_value, source, _ = await _resolve_registration(client, user_id)

                # Count the account's group chat dialogs (bounded sample) as
                # the "common groups" metric shown in the report.
                common_groups = 0
                with suppress(Exception):
                    dialog_count = 0
                    async for dialog in client.iter_dialogs():
                        if dialog.is_group or dialog.is_channel:
                            common_groups += 1
                        dialog_count += 1
                        if dialog_count >= 2000:
                            break

                return AccountAgeInfo(
                    session_name=session_path.name,
                    user_id=user_id,
                    phone=phone or "Unknown",
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    is_premium=is_premium,
                    dc_id=dc_id,
                    creation_estimate=estimate_str,
                    exact_creation_date=date_value,
                    is_scam=is_scam,
                    is_fake=is_fake,
                    is_verified=is_verified,
                    registration_source=source,
                    registration_common_groups=common_groups,
                )
            except RPCError as exc:
                LOGGER.debug("Account age RPC error: %s", exc)
                continue
            except (OSError, TimeoutError) as exc:
                LOGGER.debug("Account age connection error: %s", exc)
                continue
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Account age fetch failed: %s", exc)
                return None
            finally:
                with suppress(Exception):
                    await client.disconnect()

    return None


async def process_account_age_check(
    input_path: Path,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
    proxy: tuple | None = None,
    concurrency: int = 100,
    progress: JobProgress | None = None,
    cancel_event: asyncio.Event | None = None,
    output_dir: Path | None = None,
) -> AccountAgeResult:
    """Batch process sessions (or tdata) for accurate registration times.

    Accepts a zip of sessions, a zip of tdata folders, or a single
    ``.session`` file.  Processing is concurrent (bounded by *concurrency*,
    default 100 — tune up to thousands of sessions per job).

    When *output_dir* is given, three artifacts are produced there:

    - ``registration_report_<ts>.txt``  — detailed per-account report;
    - ``registration_all_<ts>.zip``     — session files sorted into
      ``YYYY-MM-DD`` folders by registration date;
    - ``query_failed_<ts>.zip``         — failed session files plus a
      ``failed_reasons.txt`` inside.
    """
    session_files: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="ftgc_age_work_") as work_dir:
        work = Path(work_dir)
        suffix = Path(original_name or input_path.name).suffix.lower()

        if suffix == ".zip":
            sessions = await asyncio.to_thread(
                extract_zip_sessions_safe, input_path, work
            )
            session_files = sessions
            if not session_files:
                # TData archive fallback
                tdata_work = work / "tdata"
                tdata_work.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(extract_zip_tdata_safe, input_path, tdata_work)
                tdata_dirs = await asyncio.to_thread(find_tdata_dirs, tdata_work)
                for tdir in tdata_dirs:
                    converted = await asyncio.to_thread(
                        _convert_tdata_dir_sync, tdir, work
                    )
                    session_files.extend(converted)
        elif suffix == ".session":
            target = work / Path(original_name or input_path.name).name
            shutil.copy2(input_path, target)
            session_files = [target]

        total = len(session_files)
        if progress is not None:
            progress.total = total

        accounts: list[AccountAgeInfo] = []
        failure_entries: list[tuple[str, str]] = []
        fetch_semaphore = asyncio.Semaphore(max(1, min(concurrency, total or 1)))

        async def tracked_fetch(index: int) -> AccountAgeInfo | None:
            if cancel_event is not None and cancel_event.is_set():
                raise JobCancelled()
            async with fetch_semaphore:
                info = await fetch_single_account_age(
                    session_files[index], credentials, proxy=proxy
                )
            if progress is not None:
                progress.done += 1
            return info

        infos = await asyncio.gather(
            *(tracked_fetch(index) for index in range(total))
        )

        failed = 0
        for index, info in enumerate(infos):
            if info is not None:
                accounts.append(info)
            else:
                failed += 1
                filename = session_files[index].name
                if not _is_valid_session(session_files[index]):
                    reason = "Invalid or corrupted session file"
                else:
                    reason = "Account unauthorized or expired"
                failure_entries.append((filename, reason))

        result = AccountAgeResult(
            total=total,
            checked=len(accounts),
            failed=failed,
            accounts=tuple(accounts),
            failure_entries=tuple(failure_entries),
        )

        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            report_path, classified_zip, failed_zip = await asyncio.to_thread(
                _build_outputs, work, result, session_files, output_dir
            )
            result = AccountAgeResult(
                total=total,
                checked=len(accounts),
                failed=failed,
                accounts=tuple(accounts),
                failure_entries=tuple(failure_entries),
                report_path=report_path,
                classified_zip_path=classified_zip,
                failed_zip_path=failed_zip,
            )

        return result


def _build_outputs(
    work: Path,
    result: AccountAgeResult,
    session_files: list[Path],
    output_dir: Path,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write the report txt + sorted/failed zips into *output_dir*.

    Returns (report_path, classified_zip_path, failed_zip_path).
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    report_path: Path | None = None
    if result.total > 0:
        report_path = output_dir / f"registration_report_{timestamp}.txt"
        report_path.write_text(format_registration_report(result), encoding="utf-8")

    classified_zip: Path | None = None
    if result.accounts:
        classified_root = work / "classified"
        classified_root.mkdir(exist_ok=True)
        for info in result.accounts:
            date_key = info.registration_date
            if not date_key:
                continue
            src = next(
                (p for p in session_files if p.name == info.session_name),
                None,
            )
            if src is None or not src.exists():
                continue
            dest_dir = classified_root / date_key
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest_dir / src.name)
        candidate = output_dir / f"registration_all_{timestamp}.zip"
        if _zip_folder(classified_root, candidate):
            classified_zip = candidate

    failed_zip: Path | None = None
    if result.failure_entries:
        failed_root = work / "failed"
        failed_root.mkdir(exist_ok=True)
        for name, _reason in result.failure_entries:
            src = next((p for p in session_files if p.name == name), None)
            if src is None or not src.exists():
                continue
            shutil.copy2(src, failed_root / src.name)
        (failed_root / "failed_reasons.txt").write_text(
            "\n".join(
                f"{name} | {reason}" for name, reason in result.failure_entries
            ),
            encoding="utf-8",
        )
        candidate = output_dir / f"query_failed_{timestamp}.zip"
        if _zip_folder(failed_root, candidate):
            failed_zip = candidate

    return report_path, classified_zip, failed_zip


def _zip_folder(folder: Path, out_zip: Path) -> bool:
    """Zip *folder*'s contents (recursively) into *out_zip*.

    Returns True when at least one file was archived.
    """
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    if not files:
        return False
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=path.relative_to(folder).as_posix())
    return True


def format_registration_report(res: AccountAgeResult) -> str:
    """Plain-text registration report (downloadable .txt).

    Classified by full date (Year-Month-Day); every account shows File,
    Phone, User ID, Name, Common Groups and the data source used.
    """
    lines: list[str] = [
        "Registration Time Query Report",
        "═" * 42,
        "",
        f"Total Accounts: {res.total}",
        f"Success: {res.checked}",
        f"Failed: {res.failed}",
        "",
        "Data sources:",
        f"  1. {SOURCE_LABELS['telegram_chat']}",
        f"  2. {SOURCE_LABELS['saved_messages']}",
        f"  3. {SOURCE_LABELS['estimation']}",
        "",
    ]

    if res.checked == 0 or not res.accounts:
        lines.append("No accounts in the report.")
        lines.append("")
    else:
        buckets: dict[str, list[AccountAgeInfo]] = {}
        for acc in res.accounts:
            key = acc.registration_date or "?"
            if key == "?":
                continue
            buckets.setdefault(key, []).append(acc)

        for date_key in sorted(buckets):
            block = buckets[date_key]
            lines.append(f"📅 {date_key} | {len(block)} account{'s' if len(block) > 1 else ''}")
            lines.append("─" * 42)
            for acc in sorted(block, key=lambda a: a.session_name):
                source = SOURCE_LABELS.get(acc.registration_source, "?")
                uname = f"@{acc.username}" if acc.username else "N/A"
                lines.append(f"  File: {acc.session_name}")
                lines.append(f"  Phone: {acc.phone}")
                lines.append(f"  User ID: {acc.user_id}")
                lines.append(f"  Name: {acc.full_name}")
                lines.append(f"  Username: {uname}")
                lines.append(f"  Common Groups: {acc.registration_common_groups}")
                lines.append(f"  Source: {source}")
                lines.append("")
            lines.append("")

    failed_entries = res.failure_entries
    if failed_entries:
        lines.append("Failed accounts:")
        lines.append("─" * 42)
        for name, err in failed_entries:
            lines.append(f"  File: {name}")
            lines.append(f"  Error: {err}")
            lines.append("")

    return "\n".join(lines)


def format_registration_report_summary(res: AccountAgeResult) -> str:
    """Bot chat summary message: stats + accounts per registration date."""
    lines = [
        "✅ Registration Time Query Complete",
        "",
        "Statistics:",
        f"• Total: {res.total}",
        f"• ✅ Success: {res.checked}",
        f"• ❌ Failed: {res.failed}",
        "",
        "Classified by registration date:",
    ]
    buckets: dict[str, int] = {}
    for acc in res.accounts:
        date_key = acc.registration_date
        if date_key:
            buckets[date_key] = buckets.get(date_key, 0) + 1
    if buckets:
        for date_key in sorted(buckets):
            lines.append(f"• {date_key}: {buckets[date_key]}")
    else:
        lines.append("• No accounts")
    lines.extend(["", "📄 See detailed report in files below"])
    return "\n".join(lines)


def format_account_age_report(
    res: AccountAgeResult, msgs: dict[str, str], page: int = 0
) -> str:
    if res.checked == 0 or not res.accounts:
        return msgs.get("no_sessions", "❌ No valid accounts found.")

    target_page = max(0, min(page, len(res.accounts) - 1))
    acc = res.accounts[target_page]

    username_str = f"@{html.quote(acc.username)}" if acc.username else "N/A"
    premium_str = "⭐ Yes" if acc.is_premium else "❌ No"

    badges = []
    if acc.is_verified:
        badges.append("✅ Verified")
    if acc.is_scam:
        badges.append("⚠️ Scam")
    if acc.is_fake:
        badges.append("🚫 Fake")
    badge_str = f" ({', '.join(badges)})" if badges else ""

    # Format creation date, confidence, and source
    if acc.exact_creation_date:
        created_val = f"{acc.exact_creation_date} (Exact)"
        confidence_val = "🟢 High"
        source_desc = "Community Dataset"
    elif (
        "after November 2025" in acc.creation_estimate
        or "after 11/2025" in acc.creation_estimate
    ):
        created_val = "After November 2025"
        confidence_val = "🟡 Low"
        source_desc = "Community Dataset"
    elif (
        "before August 2013" in acc.creation_estimate
        or "before 8/2013" in acc.creation_estimate
    ):
        created_val = "Before August 2013"
        confidence_val = "🟡 Low"
        source_desc = "Community Dataset"
    else:
        lines = [
            line.strip() for line in acc.creation_estimate.splitlines() if line.strip()
        ]
        created_val = lines[0] if lines else acc.creation_estimate
        # Interpolated between two dataset milestones — informative but not
        # exact, so Medium (never High) confidence.
        confidence_val = "🟡 Medium"
        source_desc = "Community Dataset"

    header = (
        f"📦 <b>Accounts ({target_page + 1}/{len(res.accounts)})</b>\n\n"
        if len(res.accounts) > 1
        else ""
    )

    divider = EmojiRegistry.divider_line()
    return (
        f"{header}"
        f"👤 <b>Account Information</b>\n"
        f"{divider}\n\n"
        f"Name        {html.quote(acc.full_name)}{badge_str}\n"
        f"Username    {username_str}\n"
        f"User ID     <code>{acc.user_id}</code>\n"
        f"Premium     {premium_str}\n"
        f"DC          {html.quote(acc.dc_name)}\n\n"
        f"📅 <b>Estimated Account Age</b>\n"
        f"{divider}\n\n"
        f"Created     {created_val}\n"
        f"Confidence  {confidence_val}\n"
        f"Source      {source_desc}\n\n"
        f"📊 <b>Statistics</b>\n"
        f"{divider}\n\n"
        f"Gifts       0\n"
        f"Rating      Level 0"
    )