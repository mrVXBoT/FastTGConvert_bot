from __future__ import annotations

import logging
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from app.services.contacts_checker import extract_zip_sessions_safe

LOGGER = logging.getLogger(__name__)

TwoFactorOperation = Literal["changed", "disabled", "reset"]
ResetOutcome = Literal["success", "pending", "failed"]


@dataclass(frozen=True)
class TwoFactorResult:
    total: int
    success: int
    failed: int
    pending: int = 0
    output_path: Path | None = None
    is_zip: bool = False
    failure_reasons: tuple[str, ...] = ()


def _is_valid_session(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            row = connection.execute("SELECT auth_key FROM sessions LIMIT 1").fetchone()
        auth_key = bytes(row[0]) if row and row[0] is not None else b""
        return len(auth_key) == 256 and any(auth_key)
    except (OSError, sqlite3.DatabaseError):
        return False


def _prepare_sessions(
    input_path: Path, original_name: str | None, prefix: str
) -> tuple[tempfile.TemporaryDirectory[str], list[Path]]:
    work_dir = tempfile.TemporaryDirectory(prefix=prefix)
    work_path = Path(work_dir.name)
    suffix = Path(original_name or input_path.name).suffix.lower()
    try:
        if suffix == ".zip":
            sessions = extract_zip_sessions_safe(input_path, work_path)
        elif suffix == ".session":
            target = work_path / Path(original_name or input_path.name).name
            shutil.copy2(input_path, target)
            sessions = [target]
        else:
            raise ValueError("unsupported_file_type")
        return work_dir, sessions
    except Exception:
        work_dir.cleanup()
        raise


def stage_two_factor_sessions(
    input_path: Path,
    work_dir: Path,
    *,
    original_name: str | None = None,
) -> list[Path]:
    """Copy/extract an upload into a persistent handler-owned workspace."""
    work_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(original_name or input_path.name).suffix.lower()
    if suffix == ".zip":
        return extract_zip_sessions_safe(input_path, work_dir)
    if suffix == ".session":
        target = work_dir / Path(original_name or input_path.name).name
        shutil.copy2(input_path, target)
        return [target]
    raise ValueError("unsupported_file_type")


async def _edit_password(
    session_path: Path,
    credentials: list[tuple[int, str]],
    *,
    current_password: str,
    new_password: str | None,
) -> bool:
    try:
        from telethon import TelegramClient  # type: ignore[import-untyped]
        from telethon.errors import (  # type: ignore[import-untyped]
            ApiIdInvalidError,
            RPCError,
        )
    except ModuleNotFoundError:
        return False

    for api_id, api_hash in credentials:
        with tempfile.TemporaryDirectory(prefix="ftgc_2fa_client_") as run_tmp:
            run_session = Path(run_tmp) / "account.session"
            shutil.copy2(session_path, run_session)
            client = TelegramClient(
                str(run_session.with_suffix("")),
                api_id,
                api_hash,
                receive_updates=False,
            )
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    return False
                changed = await client.edit_2fa(
                    current_password=current_password,
                    new_password=new_password,
                )
                if changed is True:
                    shutil.copy2(run_session, session_path)
                    return True
                return False
            except ApiIdInvalidError:
                continue
            except RPCError as exc:
                LOGGER.debug("2FA password edit rejected by Telegram: %s", exc)
                return False
            except (OSError, TimeoutError) as exc:
                LOGGER.debug("Temporary 2FA connection failure: %s", exc)
                continue
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("2FA password edit attempt failed: %s", exc)
                return False
            finally:
                with suppress(Exception):
                    await client.disconnect()
    return False


async def edit_two_factor_session(
    session_path: Path,
    credentials: list[tuple[int, str]],
    *,
    current_password: str,
    new_password: str | None = None,
) -> bool:
    """Edit 2FA for one staged account using that account's own password."""
    if not _is_valid_session(session_path) or not current_password:
        return False
    return await _edit_password(
        session_path,
        credentials,
        current_password=current_password,
        new_password=new_password,
    )


def package_two_factor_batch(
    session_files: list[Path],
    successful_indexes: set[int],
    output_dir: Path,
    operation: Literal["changed", "disabled"],
    *,
    force_zip: bool,
) -> TwoFactorResult:
    """Package every input session, separating successes and failures in ZIPs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(session_files)
    success = sum(index in successful_indexes for index in range(total))
    failed = total - success
    title = "2FA_Changed" if operation == "changed" else "2FA_Disabled"
    token = uuid4().hex[:10]

    if total == 1 and not force_zip:
        output_path = output_dir / f"{title}_{success}_Success_{token}.session"
        shutil.copy2(session_files[0], output_path)
        return TwoFactorResult(
            total=total,
            success=success,
            failed=failed,
            output_path=output_path,
            is_zip=False,
        )

    output_path = output_dir / f"{title}_{success}_Success_{token}.zip"
    used_names: set[str] = set()
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, session_path in enumerate(session_files):
            folder = "success" if index in successful_indexes else "failed"
            archive_name = session_path.name
            candidate = f"{folder}/{archive_name}"
            if candidate in used_names:
                candidate = f"{folder}/{session_path.stem}_{index + 1}.session"
            used_names.add(candidate)
            archive.write(session_path, arcname=candidate)

    return TwoFactorResult(
        total=total,
        success=success,
        failed=failed,
        output_path=output_path,
        is_zip=True,
    )


async def _reset_password(
    session_path: Path, credentials: list[tuple[int, str]]
) -> tuple[ResetOutcome, str | None]:
    try:
        from telethon import TelegramClient, functions  # type: ignore[import-untyped]
        from telethon.errors import (  # type: ignore[import-untyped]
            ApiIdInvalidError,
            RPCError,
        )
        from telethon.tl.types.account import (  # type: ignore[import-untyped]
            ResetPasswordOk,
            ResetPasswordRequestedWait,
        )
    except ModuleNotFoundError:
        return "failed", "telethon_unavailable"

    for api_id, api_hash in credentials:
        with tempfile.TemporaryDirectory(prefix="ftgc_2fa_reset_client_") as run_tmp:
            run_session = Path(run_tmp) / "account.session"
            shutil.copy2(session_path, run_session)
            client = TelegramClient(
                str(run_session.with_suffix("")),
                api_id,
                api_hash,
                receive_updates=False,
            )
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    return "failed", "unauthorized_session"
                response = await client(functions.account.ResetPasswordRequest())
                if isinstance(response, ResetPasswordOk):
                    shutil.copy2(run_session, session_path)
                    return "success", None
                if isinstance(response, ResetPasswordRequestedWait):
                    return "pending", None
                response_name = type(response).__name__
                LOGGER.warning("2FA reset returned %s", response_name)
                if response_name == "ResetPasswordFailedWait":
                    return "failed", "reset_failed_wait"
                return "failed", "unexpected_reset_response"
            except ApiIdInvalidError:
                continue
            except RPCError as exc:
                reason = _reset_error_reason(exc)
                LOGGER.warning(
                    "2FA reset rejected by Telegram: %s (%s)",
                    type(exc).__name__,
                    reason,
                )
                return "failed", reason
            except (OSError, TimeoutError) as exc:
                LOGGER.debug("Temporary 2FA reset connection failure: %s", exc)
                continue
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("2FA reset attempt failed: %s", type(exc).__name__)
                return "failed", "internal_reset_error"
            finally:
                with suppress(Exception):
                    await client.disconnect()
    return "failed", "api_credentials_or_network_failed"


def _reset_error_reason(error: Exception) -> str:
    return {
        "FreshResetAuthorisationForbiddenError": "fresh_authorization_forbidden",
        "PasswordRecoveryNaError": "recovery_email_unavailable",
        "PasswordTooFreshError": "password_too_fresh",
        "ResetRequestMissingError": "reset_request_missing",
        "PhonePasswordFloodError": "too_many_attempts",
        "FloodWaitError": "flood_wait",
    }.get(type(error).__name__, "telegram_rejected_reset")


def _package_successes(
    success_files: list[Path],
    output_dir: Path,
    operation: TwoFactorOperation,
    *,
    force_zip: bool,
) -> tuple[Path | None, bool]:
    if not success_files:
        return None, False

    output_dir.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    title = {
        "changed": "2FA_Changed_Success",
        "disabled": "2FA_Disabled_Success",
        "reset": "2FA_Reset",
    }[operation]
    count = len(success_files)

    if count == 1 and not force_zip:
        output_path = output_dir / f"{title}_{count}_{token}.session"
        shutil.copy2(success_files[0], output_path)
        return output_path, False

    output_path = output_dir / f"{title}_{count}_{token}.zip"
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        used_names: set[str] = set()
        for index, session_path in enumerate(success_files, start=1):
            archive_name = session_path.name
            if archive_name in used_names:
                archive_name = f"{session_path.stem}_{index}.session"
            used_names.add(archive_name)
            archive.write(session_path, arcname=archive_name)
    return output_path, True


async def _process_password_edit(
    input_path: Path,
    output_dir: Path,
    current_password: str,
    new_password: str | None,
    credentials: list[tuple[int, str]],
    operation: Literal["changed", "disabled"],
    original_name: str | None,
) -> TwoFactorResult:
    force_zip = Path(original_name or input_path.name).suffix.lower() == ".zip"
    work_dir, session_files = _prepare_sessions(
        input_path, original_name, f"ftgc_2fa_{operation}_"
    )
    try:
        success_files: list[Path] = []
        failed = 0
        for session_path in session_files:
            if not _is_valid_session(session_path):
                failed += 1
                continue
            if await _edit_password(
                session_path,
                credentials,
                current_password=current_password,
                new_password=new_password,
            ):
                success_files.append(session_path)
            else:
                failed += 1

        output_path, is_zip = _package_successes(
            success_files, output_dir, operation, force_zip=force_zip
        )
        return TwoFactorResult(
            total=len(session_files),
            success=len(success_files),
            failed=failed,
            output_path=output_path,
            is_zip=is_zip,
        )
    finally:
        work_dir.cleanup()


async def process_change_2fa(
    input_path: Path,
    output_dir: Path,
    old_password: str,
    new_password: str,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
) -> TwoFactorResult:
    if not old_password or not new_password:
        raise ValueError("password_required")
    return await _process_password_edit(
        input_path,
        output_dir,
        old_password,
        new_password,
        credentials,
        "changed",
        original_name,
    )


async def process_disable_2fa(
    input_path: Path,
    output_dir: Path,
    current_password: str,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
) -> TwoFactorResult:
    if not current_password:
        raise ValueError("password_required")
    return await _process_password_edit(
        input_path,
        output_dir,
        current_password,
        None,
        credentials,
        "disabled",
        original_name,
    )


async def process_reset_2fa(
    input_path: Path,
    output_dir: Path,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
) -> TwoFactorResult:
    force_zip = Path(original_name or input_path.name).suffix.lower() == ".zip"
    work_dir, session_files = _prepare_sessions(
        input_path, original_name, "ftgc_2fa_reset_"
    )
    try:
        success_files: list[Path] = []
        failed = 0
        pending = 0
        failure_reasons: list[str] = []
        for session_path in session_files:
            if not _is_valid_session(session_path):
                failed += 1
                failure_reasons.append("invalid_session")
                continue
            outcome, reason = await _reset_password(session_path, credentials)
            if outcome == "success":
                success_files.append(session_path)
            elif outcome == "pending":
                pending += 1
            else:
                failed += 1
                if reason:
                    failure_reasons.append(reason)

        output_path, is_zip = _package_successes(
            success_files, output_dir, "reset", force_zip=force_zip
        )
        return TwoFactorResult(
            total=len(session_files),
            success=len(success_files),
            failed=failed,
            pending=pending,
            output_path=output_path,
            is_zip=is_zip,
            failure_reasons=tuple(dict.fromkeys(failure_reasons)),
        )
    finally:
        work_dir.cleanup()
