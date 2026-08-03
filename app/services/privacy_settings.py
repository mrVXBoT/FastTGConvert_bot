"""privacy_settings.py — Telegram Account Privacy Settings Management Service.

Applies privacy rules to single or multiple Telegram accounts via Telethon MTProto API.

Supported Privacy Rules:
  • Last Seen (StatusTimestamp)
  • Phone Number
  • Profile Photos
  • Forwarded Messages
  • Calls
  • Peer-to-Peer Calls
  • Group Invites
  • Voice Messages

Supported Presets:
  • Maximum Privacy: Nobody for sensitive rules; My Contacts for photo & invites.
  • Medium Privacy:  My Contacts for sensitive rules; Everybody for photo & voice.
  • Open / Public Privacy: Everybody for all rules.
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from telethon import TelegramClient  # type: ignore[import-untyped]
from telethon.errors import (  # type: ignore[import-untyped]
    AuthKeyUnregisteredError,
    FloodWaitError,
    PasswordHashInvalidError,
    PrivacyKeyInvalidError,
    RPCError,
    SessionPasswordNeededError,
    UserDeactivatedError,
)
from telethon.tl.functions.account import (  # type: ignore[import-untyped]
    GetPrivacyRequest,
    SetPrivacyRequest,
)
from telethon.tl.types import (  # type: ignore[import-untyped]
    InputPrivacyKeyChatInvite,
    InputPrivacyKeyForwards,
    InputPrivacyKeyPhoneCall,
    InputPrivacyKeyPhoneNumber,
    InputPrivacyKeyPhoneP2P,
    InputPrivacyKeyProfilePhoto,
    InputPrivacyKeyStatusTimestamp,
    InputPrivacyKeyVoiceMessages,
    InputPrivacyValueAllowAll,
    InputPrivacyValueAllowContacts,
    InputPrivacyValueDisallowAll,
    PrivacyValueAllowAll,
    PrivacyValueAllowContacts,
    PrivacyValueDisallowAll,
)

from app.services.contacts_checker import extract_zip_sessions_safe

LOGGER = logging.getLogger(__name__)

# ── Mapping Telethon Types ───────────────────────────────────────────────────

RULE_KEY_CLASSES: dict[str, type] = {
    "last_seen": InputPrivacyKeyStatusTimestamp,
    "phone_number": InputPrivacyKeyPhoneNumber,
    "profile_photo": InputPrivacyKeyProfilePhoto,
    "forwarded_messages": InputPrivacyKeyForwards,
    "calls": InputPrivacyKeyPhoneCall,
    "p2p_calls": InputPrivacyKeyPhoneP2P,
    "group_invites": InputPrivacyKeyChatInvite,
    "voice_messages": InputPrivacyKeyVoiceMessages,
}

RULE_VALUE_FACTORY: dict[str, Any] = {
    "everybody": lambda: [InputPrivacyValueAllowAll()],
    "contacts": lambda: [InputPrivacyValueAllowContacts()],
    "nobody": lambda: [InputPrivacyValueDisallowAll()],
}

PRESETS: dict[str, dict[str, str]] = {
    "maximum": {
        "last_seen": "nobody",
        "phone_number": "nobody",
        "profile_photo": "contacts",
        "forwarded_messages": "nobody",
        "calls": "nobody",
        "p2p_calls": "nobody",
        "group_invites": "contacts",
        "voice_messages": "nobody",
    },
    "medium": {
        "last_seen": "contacts",
        "phone_number": "nobody",
        "profile_photo": "everybody",
        "forwarded_messages": "contacts",
        "calls": "contacts",
        "p2p_calls": "contacts",
        "group_invites": "contacts",
        "voice_messages": "everybody",
    },
    "open": {
        "last_seen": "everybody",
        "phone_number": "everybody",
        "profile_photo": "everybody",
        "forwarded_messages": "everybody",
        "calls": "everybody",
        "p2p_calls": "everybody",
        "group_invites": "everybody",
        "voice_messages": "everybody",
    },
}


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RulePrivacyStatus:
    rule_key: str
    status: str       # "applied" | "unsupported" | "flood_wait" | "unauthorized" | "failed"
    detail: str | None = None


@dataclass(frozen=True)
class SessionPrivacyDetail:
    session_name: str
    status: str       # "ok" | "failed" | "unauthorized"
    rule_results: dict[str, RulePrivacyStatus]
    error: str | None = None


@dataclass(frozen=True)
class PrivacySettingsResult:
    total: int
    succeeded: int
    failed: int
    preset_name: str | None
    details: list[SessionPrivacyDetail]


# ── Service Functions ─────────────────────────────────────────────────────────

async def get_account_privacy_rules(
    client: TelegramClient,
) -> dict[str, str]:
    """Retrieve current privacy settings from Telegram server for all supported keys."""
    current_rules: dict[str, str] = {}
    for key_name, key_cls in RULE_KEY_CLASSES.items():
        try:
            res = await client(GetPrivacyRequest(key=key_cls()))
            if hasattr(res, "rules") and res.rules:
                val = "unknown"
                for r in res.rules:
                    if isinstance(r, PrivacyValueAllowAll):
                        val = "everybody"
                        break
                    elif isinstance(r, PrivacyValueAllowContacts):
                        val = "contacts"
                        break
                    elif isinstance(r, PrivacyValueDisallowAll):
                        val = "nobody"
                        break
                current_rules[key_name] = val
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("GetPrivacyRequest failed for %s: %s", key_name, exc)
    return current_rules


async def apply_session_privacy(
    client: TelegramClient,
    rules: dict[str, str],
    verify: bool = True,
) -> dict[str, RulePrivacyStatus]:
    """Apply a map of {rule_key: choice_value} to an active Telethon client.

    Handles each rule independently so failure or restrictions on one rule (e.g. Premium-only
    voice_messages) do not fail the rest of the rules or the entire session.
    """
    rule_results: dict[str, RulePrivacyStatus] = {}

    for key_name, val_choice in rules.items():
        if key_name not in RULE_KEY_CLASSES or val_choice not in RULE_VALUE_FACTORY:
            continue
        key_cls = RULE_KEY_CLASSES[key_name]
        rule_list = RULE_VALUE_FACTORY[val_choice]()

        try:
            req = SetPrivacyRequest(key=key_cls(), rules=rule_list)
            await client(req)

            # Verification step: Call GetPrivacyRequest to confirm server state
            if verify:
                verified_val = await get_account_privacy_rule_value(client, key_cls)
                if verified_val and verified_val != val_choice:
                    LOGGER.warning(
                        "Mismatch for %s: requested %s but server returned %s",
                        key_name, val_choice, verified_val
                    )

            rule_results[key_name] = RulePrivacyStatus(
                rule_key=key_name,
                status="applied",
            )
        except PrivacyKeyInvalidError as pki:
            LOGGER.info("Privacy key %s not supported on this account: %s", key_name, pki)
            rule_results[key_name] = RulePrivacyStatus(
                rule_key=key_name,
                status="unsupported",
                detail="Privacy key invalid or unsupported",
            )
        except FloodWaitError as fw:
            LOGGER.warning("FloodWait of %d seconds while setting %s", fw.seconds, key_name)
            rule_results[key_name] = RulePrivacyStatus(
                rule_key=key_name,
                status="flood_wait",
                detail=f"FloodWait ({fw.seconds}s)",
            )
        except RPCError as rpc_err:
            LOGGER.warning("RPCError setting %s: %s", key_name, rpc_err)
            rule_results[key_name] = RulePrivacyStatus(
                rule_key=key_name,
                status="failed",
                detail=str(rpc_err),
            )
        except Exception as exc:
            LOGGER.exception("Unexpected error setting %s", key_name)
            rule_results[key_name] = RulePrivacyStatus(
                rule_key=key_name,
                status="failed",
                detail=str(exc),
            )

    return rule_results


async def get_account_privacy_rule_value(
    client: TelegramClient,
    key_cls: type,
) -> str | None:
    """Helper to fetch a single privacy rule value from Telegram server."""
    try:
        res = await client(GetPrivacyRequest(key=key_cls()))
        if hasattr(res, "rules") and res.rules:
            for r in res.rules:
                if isinstance(r, PrivacyValueAllowAll):
                    return "everybody"
                if isinstance(r, PrivacyValueAllowContacts):
                    return "contacts"
                if isinstance(r, PrivacyValueDisallowAll):
                    return "nobody"
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("GetPrivacyRequest exception: %s", exc)
    return None


async def process_single_session_privacy(
    session_file: Path,
    password: str | None,
    rules: dict[str, str],
    api_id: int,
    api_hash: str,
    proxy: tuple | None = None,
) -> SessionPrivacyDetail:
    """Process privacy settings update for a single .session file."""
    session_name = session_file.name
    client = TelegramClient(
        str(session_file),
        api_id,
        api_hash,
        device_model="FastTGConvert Bot",
        system_version="1.0.0",
        app_version="1.0.0",
        proxy=proxy,
    )

    try:
        await client.connect()
        if not await client.is_user_authorized():
            if password:
                try:
                    await client.sign_in(password=password)
                except (PasswordHashInvalidError, SessionPasswordNeededError):
                    return SessionPrivacyDetail(
                        session_name=session_name,
                        status="unauthorized",
                        rule_results={},
                        error="Invalid 2FA Password",
                    )
                except Exception as auth_err:  # noqa: BLE001
                    return SessionPrivacyDetail(
                        session_name=session_name,
                        status="unauthorized",
                        rule_results={},
                        error=f"Auth error: {auth_err}",
                    )
            else:
                return SessionPrivacyDetail(
                    session_name=session_name,
                    status="unauthorized",
                    rule_results={},
                    error="Unauthorized / session inactive",
                )

        rule_results = await apply_session_privacy(client, rules)
        # Session is OK if at least one rule applied or skipped gracefully
        has_applied = any(r.status in ("applied", "unsupported") for r in rule_results.values())
        overall_status = "ok" if has_applied else "failed"

        return SessionPrivacyDetail(
            session_name=session_name,
            status=overall_status,
            rule_results=rule_results,
        )

    except (AuthKeyUnregisteredError, UserDeactivatedError):
        return SessionPrivacyDetail(
            session_name=session_name,
            status="unauthorized",
            rule_results={},
            error="Session expired or deactivated",
        )
    except FloodWaitError as fw:
        return SessionPrivacyDetail(
            session_name=session_name,
            status="failed",
            rule_results={},
            error=f"FloodWait ({fw.seconds}s)",
        )
    except Exception as exc:
        LOGGER.exception("Error processing privacy for session %s", session_name)
        return SessionPrivacyDetail(
            session_name=session_name,
            status="failed",
            rule_results={},
            error=str(exc),
        )
    finally:
        try:
            await asyncio.wait_for(client.disconnect(), timeout=3.0)
        except Exception as disc_exc:  # noqa: BLE001
            LOGGER.debug("Client disconnect exception: %s", disc_exc)


async def process_privacy_settings(
    input_path: Path,
    password: str | None = None,
    rules: dict[str, str] | None = None,
    preset_name: str | None = None,
    api_id: int = 6,
    api_hash: str = "eb06d4abfb49dc3eeb1aeb98ae0f581e",
    proxy: tuple | None = None,
) -> PrivacySettingsResult:
    """Process privacy settings update for a single .session file or ZIP archive of sessions."""
    effective_rules = dict(PRESETS.get(preset_name, {})) if preset_name else dict(rules or {})
    if not effective_rules:
        effective_rules = PRESETS["maximum"]

    session_files: list[Path] = []
    temp_dir: Path | None = None

    if input_path.suffix.lower() == ".zip":
        temp_dir = Path(tempfile.mkdtemp(prefix="ftgc_privacy_"))
        session_files = extract_zip_sessions_safe(input_path, temp_dir)
    elif input_path.suffix.lower() == ".session":
        session_files = [input_path]

    if not session_files:
        if temp_dir:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        return PrivacySettingsResult(
            total=0, succeeded=0, failed=0, preset_name=preset_name, details=[]
        )

    details: list[SessionPrivacyDetail] = []
    succeeded = 0
    failed = 0

    try:
        for sf in session_files:
            detail = await process_single_session_privacy(
                sf, password, effective_rules, api_id, api_hash, proxy=proxy
            )
            details.append(detail)
            if detail.status == "ok":
                succeeded += 1
            else:
                failed += 1
    finally:
        if temp_dir:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    return PrivacySettingsResult(
        total=len(session_files),
        succeeded=succeeded,
        failed=failed,
        preset_name=preset_name,
        details=details,
    )
