from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import zipfile
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from app.services.file_merge import _is_valid_sqlite_session
from app.services.jobs import JobCancelled, JobProgress
from app.services.session_to_tdata import _ensure_opentele_patched

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccountProfileInfo:
    user_id: int
    phone: str
    first_name: str
    last_name: str
    username: str
    about: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ProfileSetupResult:
    total: int
    modified: int
    skipped: int
    failed: int
    output_path: Path | None = None
    is_zip: bool = False


async def fetch_account_profile(
    session_file: Path,
    credentials: list[tuple[int, str]],
) -> AccountProfileInfo | None:
    if not credentials or not session_file.exists():
        return None

    try:
        from telethon import TelegramClient, functions  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        LOGGER.error("Telethon not installed for fetch profile")
        return None

    with tempfile.TemporaryDirectory(prefix="ftgc_fetch_prof_") as tmp:
        run_sess = Path(tmp) / "account.session"
        shutil.copy2(session_file, run_sess)
        stem = str(run_sess.with_suffix(""))

        for api_id, api_hash in credentials:
            client = None
            try:
                from app.services.device_params import get_stable_device_params
                device_kwargs = get_stable_device_params(session_file)
                client = TelegramClient(stem, api_id, api_hash, receive_updates=False, **device_kwargs)
                await client.connect()
                if not await client.is_user_authorized():
                    await client.disconnect()
                    # Dead auth key: unauthorized under any api_id.
                    break

                me = await client.get_me()
                uid = getattr(me, "id", 0)
                phone = str(getattr(me, "phone", "") or "")
                first_name = str(getattr(me, "first_name", "") or "")
                last_name = str(getattr(me, "last_name", "") or "")
                username = str(getattr(me, "username", "") or "")

                about = ""
                with suppress(Exception):
                    full = await client(functions.users.GetFullUserRequest(id="me"))
                    full_user = getattr(full, "full_user", None)
                    if full_user:
                        about = str(getattr(full_user, "about", "") or "")

                await client.disconnect()
                return AccountProfileInfo(
                    user_id=uid,
                    phone=phone,
                    first_name=first_name,
                    last_name=last_name,
                    username=username,
                    about=about,
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Fetch profile failed with api_id=%d: %s", api_id, exc)
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()

    return None


async def prefetch_account_profiles(
    session_files: list[Path],
    credentials: list[tuple[int, str]],
    *,
    concurrency: int = 50,
    progress: JobProgress | None = None,
    cancel_event: asyncio.Event | None = None,
) -> list[AccountProfileInfo | None]:
    """Fetch all session profiles concurrently (bounded by *concurrency*).

    Returns a list aligned with *session_files*; ``None`` marks sessions
    that failed to authorize.  Live progress/cancel support included.
    """
    total = len(session_files)
    if progress is not None:
        progress.total = total

    semaphore = asyncio.Semaphore(max(1, min(concurrency, total or 1)))

    async def tracked(index: int) -> AccountProfileInfo | None:
        if cancel_event is not None and cancel_event.is_set():
            raise JobCancelled()
        async with semaphore:
            info = await fetch_account_profile(session_files[index], credentials)
        if progress is not None:
            progress.done += 1
        return info

    return await asyncio.gather(*(tracked(i) for i in range(total)))


async def update_account_profile(
    session_file: Path,
    credentials: list[tuple[int, str]],
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    username: str | None = None,
    about: str | None = None,
    photo_path: Path | None = None,
) -> bool:
    if not credentials or not session_file.exists():
        return False

    try:
        from telethon import TelegramClient, functions  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        LOGGER.error("Telethon not installed for update profile")
        return False

    with tempfile.TemporaryDirectory(prefix="ftgc_update_prof_") as tmp:
        run_sess = Path(tmp) / "account.session"
        shutil.copy2(session_file, run_sess)
        stem = str(run_sess.with_suffix(""))

        for api_id, api_hash in credentials:
            client = None
            try:
                from app.services.device_params import get_stable_device_params
                device_kwargs = get_stable_device_params(session_file)
                client = TelegramClient(stem, api_id, api_hash, receive_updates=False, **device_kwargs)
                await client.connect()
                if not await client.is_user_authorized():
                    await client.disconnect()
                    # Dead auth key: unauthorized under any api_id.
                    break

                applied = False
                if first_name is not None or last_name is not None or about is not None:
                    me = await client.get_me()
                    cur_fn = (
                        first_name
                        if first_name is not None
                        else str(getattr(me, "first_name", "") or "")
                    )
                    cur_ln = (
                        last_name
                        if last_name is not None
                        else str(getattr(me, "last_name", "") or "")
                    )
                    kwargs: dict[str, str] = {
                        "first_name": cur_fn,
                        "last_name": cur_ln,
                    }
                    if about is not None:
                        kwargs["about"] = about
                    await client(functions.account.UpdateProfileRequest(**kwargs))
                    applied = True

                if username is not None:
                    clean_un = username.lstrip("@").strip()
                    try:
                        await client(
                            functions.account.UpdateUsernameRequest(username=clean_un)
                        )
                        applied = True
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.warning("Username update skipped (%s): %s", clean_un, exc)

                if photo_path is not None and photo_path.exists():
                    try:
                        uploaded = await client.upload_file(str(photo_path))
                        await client(
                            functions.photos.UploadProfilePhotoRequest(file=uploaded)
                        )
                        applied = True
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.warning("Photo upload skipped: %s", exc)

                if applied:
                    shutil.copy2(run_sess, session_file)
                await client.disconnect()
                return applied
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Update profile failed with api_id=%d: %s", api_id, exc)
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()

    return False


def package_profile_setup_results(
    session_files: list[Path],
    output_dir: Path,
    modified_count: int,
    skipped_count: int,
    failed_count: int,
    *,
    original_name: str | None = None,
) -> ProfileSetupResult:
    _ensure_opentele_patched()
    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(session_files)

    valid_files = [
        f for f in session_files if f.exists() and _is_valid_sqlite_session(f)
    ]
    output_path: Path | None = None
    is_zip = False

    if valid_files:
        if len(valid_files) == 1 and total == 1:
            output_path = output_dir / f"Profile_Setup_1_{uuid4().hex[:6]}.session"
            shutil.copy2(valid_files[0], output_path)
        else:
            is_zip = True
            output_path = (
                output_dir / f"Profile_Setup_{len(valid_files)}_{uuid4().hex[:6]}.zip"
            )
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
                used_names: set[str] = set()
                for idx, sfile in enumerate(valid_files, start=1):
                    arcname = sfile.name
                    if arcname in used_names:
                        arcname = f"{sfile.stem}_{idx}.session"
                    used_names.add(arcname)
                    archive.write(sfile, arcname=arcname)

    return ProfileSetupResult(
        total=total,
        modified=modified_count,
        skipped=skipped_count,
        failed=failed_count,
        output_path=output_path,
        is_zip=is_zip,
    )
