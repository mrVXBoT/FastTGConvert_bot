import bisect
import datetime
import logging
import shutil
import sqlite3
import tempfile
import threading
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from aiogram import html

from app.services.contacts_checker import extract_zip_sessions_safe
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

    month_name = _MONTH_NAMES[est_date.month - 1]
    month_abbr = month_name[:3]

    if months_diff < 1:
        rel_str = "newer than 1 month"
    elif months_diff < 12:
        rel_str = f"{months_diff} month{'s' if months_diff > 1 else ''} ago"
    else:
        years = months_diff // 12
        rel_str = f"{years} year{'s' if years > 1 else ''} old"

    created_str = (
        f"~ {est_date.day}/{est_date.month}/{est_date.year}\n"
        f"Estimated {est_date.day} {month_abbr} {est_date.year} ({rel_str})"
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

    @property
    def dc_name(self) -> str:
        return DC_LOCATIONS.get(self.dc_id, f"DC{self.dc_id}")

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.last_name]
        name = " ".join(p for p in parts if p).strip()
        return name if name else "N/A"


@dataclass(frozen=True)
class AccountAgeResult:
    total: int
    checked: int
    failed: int
    accounts: tuple[AccountAgeInfo, ...]


def _is_valid_session(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT auth_key FROM sessions LIMIT 1").fetchone()
        auth_key = bytes(row[0]) if row and row[0] is not None else b""
        return len(auth_key) == 256 and any(auth_key)
    except (OSError, sqlite3.DatabaseError):
        return False


async def fetch_single_account_age(
    session_path: Path,
    credentials: list[tuple[int, str]],
    proxy: tuple | None = None,
) -> AccountAgeInfo | None:
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
            client = TelegramClient(
                str(run_session.with_suffix("")),
                api_id,
                api_hash,
                receive_updates=False,
                proxy=proxy,
            )
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    return None

                me = await client.get_me()
                if not me:
                    return None

                user_id = me.id
                phone = getattr(me, "phone", "") or "Unknown"
                username = getattr(me, "username", "") or ""
                first_name = getattr(me, "first_name", "") or ""
                last_name = getattr(me, "last_name", "") or ""
                is_premium = bool(getattr(me, "premium", False))
                is_scam = bool(getattr(me, "scam", False))
                is_fake = bool(getattr(me, "fake", False))
                is_verified = bool(getattr(me, "verified", False))

                dc_id = getattr(client.session, "dc_id", 0) or 0

                _, _, estimate_str = estimate_account_creation(user_id)

                exact_date_str: str | None = None
                with suppress(Exception):
                    # Check for earliest service message from Telegram (777000)
                    messages = await client.get_messages(777000, limit=1, reverse=True)
                    if messages and len(messages) > 0 and messages[0].date:
                        msg_date = messages[0].date
                        exact_date_str = msg_date.strftime("%Y-%m-%d")

                return AccountAgeInfo(
                    session_name=session_path.name,
                    user_id=user_id,
                    phone=phone,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    is_premium=is_premium,
                    dc_id=dc_id,
                    creation_estimate=estimate_str,
                    exact_creation_date=exact_date_str,
                    is_scam=is_scam,
                    is_fake=is_fake,
                    is_verified=is_verified,
                )
            except RPCError as exc:
                LOGGER.debug("Account age Telethon RPC error: %s", exc)
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
) -> AccountAgeResult:
    """Extract sessions and fetch account age information for all accounts."""
    with tempfile.TemporaryDirectory(prefix="ftgc_age_work_") as work_dir:
        work_path = Path(work_dir)
        suffix = Path(original_name or input_path.name).suffix.lower()

        if suffix == ".zip":
            sessions = extract_zip_sessions_safe(input_path, work_path)
        elif suffix == ".session":
            target = work_path / Path(original_name or input_path.name).name
            shutil.copy2(input_path, target)
            sessions = [target]
        else:
            return AccountAgeResult(total=0, checked=0, failed=0, accounts=())

        total = len(sessions)
        accounts: list[AccountAgeInfo] = []
        failed = 0

        for session_file in sessions:
            info = await fetch_single_account_age(session_file, credentials, proxy=proxy)
            if info is not None:
                accounts.append(info)
            else:
                failed += 1

        return AccountAgeResult(
            total=total,
            checked=len(accounts),
            failed=failed,
            accounts=tuple(accounts),
        )


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
    elif (
        "after November 2025" in acc.creation_estimate
        or "after 11/2025" in acc.creation_estimate
    ):
        created_val = "After November 2025"
        confidence_val = "🟡 Low"
    elif (
        "before August 2013" in acc.creation_estimate
        or "before 8/2013" in acc.creation_estimate
    ):
        created_val = "Before August 2013"
        confidence_val = "🟡 Low"
    else:
        lines = [
            line.strip() for line in acc.creation_estimate.splitlines() if line.strip()
        ]
        created_val = lines[0] if lines else acc.creation_estimate
        # Interpolated between two dataset milestones — informative but not
        # exact, so Medium (never High) confidence.
        confidence_val = "🟡 Medium"

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
        f"Source      Community Dataset\n\n"
        f"📊 <b>Statistics</b>\n"
        f"{divider}\n\n"
        f"Gifts       0\n"
        f"Rating      Level 0"
    )
