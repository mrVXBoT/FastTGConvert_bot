"""
Live spam-status checker via @SpamBot.

Design principles
-----------------
* Credentials are rotated ONLY for credential-level errors (ApiIdInvalid).
* Account-level errors (FloodWait, deactivated, banned) stop immediately.
* Network errors (OSError) are retried with exponential back-off on the same
  credential pair before giving up.
* 2FA accounts (SessionPasswordNeeded) are reported as ``active`` – the session
  is valid and the account is reachable; we simply cannot verify spam status.
* Credential exhaustion is ``inconclusive`` (not ``invalid``) because it does
  not prove the session is broken.

Error → result mapping
-----------------------
| Telethon error              | Result        | Rationale                         |
|-----------------------------|---------------|-----------------------------------|
| ApiIdInvalidError           | try next cred | credential is invalid, not session |
| AuthKeyDuplicatedError      | invalid       | session revoked by Telegram        |
| AuthKeyError /              | invalid       | session key missing / unregistered |
|   AuthKeyUnregisteredError  |               |                                    |
| FloodWaitError (≤ limit)    | sleep + retry | account rate-limit, wait it out    |
| FloodWaitError (> limit)    | inconclusive  | can't wait this long               |
| UserDeactivatedError /      | banned        | account gone permanently           |
|   UserDeactivatedBanError   |               |                                    |
| PhoneNumberBannedError      | banned        | permanently banned by Telegram     |
| SessionPasswordNeededError  | active        | session works; 2FA set after auth  |
| OSError (up to MAX_RETRIES) | inconclusive  | transient network issue            |
| @SpamBot timeout            | inconclusive  | can't determine spam status        |
| All credentials exhausted   | inconclusive  | not proven invalid                 |

Security notes
--------------
* No auth_key, phone number, or session bytes are written to any log.
* Original session file is never modified; a copy is used.
* ``receive_updates=False`` suppresses live update ingestion.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any, Literal, cast

LOGGER = logging.getLogger(__name__)

_SPAMBOT_USERNAME = "SpamBot"

# FloodWait threshold: if Telegram asks us to wait longer than this we give up
# rather than blocking the handler for too long.
_MAX_FLOOD_WAIT_SECONDS = 30

# How many times to retry a single credential pair after an OSError.
_MAX_NETWORK_RETRIES = 2
_NETWORK_BACKOFF_BASE = 2  # seconds; doubled on each retry

# Phrases indicating a clean (unrestricted) account.
_CLEAN_KEYWORDS = (
    "good news",
    "no limits",
    "not limited",
    "can continue",
    "no current",
    "حسابك لم",  # Arabic: your account has not…
    "ваш аккаунт не",  # Russian: your account has not…
)

# Phrases indicating a spam-restricted (but potentially reversible) account.
_SPAM_KEYWORDS = (
    "limited",
    "restricted",
    "spam",
    "your account has been",
    "محدود",  # Farsi/Arabic: limited
    "заблокирован",  # Russian: blocked
    "ограничен",  # Russian: restricted
)

# Five distinct outcomes; mapped to SessionCheckResult fields by session_checker.
SpamStatus = Literal["active", "frozen", "banned", "invalid", "inconclusive"]


async def check_spam_via_spambot(
    session_path: Path,
    credentials: list[tuple[int, str]],
    timeout: int = 15,
) -> SpamStatus:
    """
    Connect with *session_path* and query @SpamBot for the account's spam status.

    Parameters
    ----------
    session_path:
        Path to the ``.session`` file (must already be a structural-check pass).
    credentials:
        Ordered list of ``(api_id, api_hash)`` pairs.  Rotation only happens
        when Telegram reports that a specific api_id is invalid.
    timeout:
        Seconds to wait for @SpamBot's reply.

    Returns
    -------
    One of ``"active"``, ``"frozen"``, ``"banned"``, ``"invalid"``,
    or ``"inconclusive"``.
    """
    if not credentials:
        LOGGER.warning("No API credentials configured; cannot run live spam check")
        return "inconclusive"

    try:
        from telethon import TelegramClient  # type: ignore[import-untyped]
        from telethon.errors import (  # type: ignore[import-untyped]
            ApiIdInvalidError,
            AuthKeyDuplicatedError,
            AuthKeyError,
            AuthKeyUnregisteredError,
            FloodWaitError,
            PhoneNumberBannedError,
            SessionPasswordNeededError,
            UserDeactivatedBanError,
            UserDeactivatedError,
        )
    except ModuleNotFoundError:
        LOGGER.error("telethon is not installed; cannot run spam check")
        return "inconclusive"

    with tempfile.TemporaryDirectory(prefix="ftgc_spam_") as tmp:
        tmp_session = Path(tmp) / "check.session"
        shutil.copy2(session_path, tmp_session)
        session_str = str(tmp_session.with_suffix(""))

        for api_id, api_hash in credentials:
            result = await _try_one_credential(
                session_str=session_str,
                api_id=api_id,
                api_hash=api_hash,
                timeout=timeout,
                TelegramClient=TelegramClient,
                ApiIdInvalidError=ApiIdInvalidError,
                AuthKeyDuplicatedError=AuthKeyDuplicatedError,
                AuthKeyError=AuthKeyError,
                AuthKeyUnregisteredError=AuthKeyUnregisteredError,
                FloodWaitError=FloodWaitError,
                PhoneNumberBannedError=PhoneNumberBannedError,
                SessionPasswordNeededError=SessionPasswordNeededError,
                UserDeactivatedBanError=UserDeactivatedBanError,
                UserDeactivatedError=UserDeactivatedError,
            )
            if result == "_try_next":
                continue
            return cast(SpamStatus, result)

        LOGGER.warning(
            "All %d credential pairs exhausted without a definitive result",
            len(credentials),
        )
        return "inconclusive"


async def _try_one_credential(
    session_str: str,
    api_id: int,
    api_hash: str,
    timeout: int,
    *,
    TelegramClient: Any,
    ApiIdInvalidError: type[BaseException],
    AuthKeyDuplicatedError: type[BaseException],
    AuthKeyError: type[BaseException],
    AuthKeyUnregisteredError: type[BaseException],
    FloodWaitError: Any,
    PhoneNumberBannedError: type[BaseException],
    SessionPasswordNeededError: type[BaseException],
    UserDeactivatedBanError: type[BaseException],
    UserDeactivatedError: type[BaseException],
) -> SpamStatus | str:
    """
    Attempt the spam check with one ``(api_id, api_hash)`` pair.

    Returns a ``SpamStatus`` string on a definitive outcome, or the sentinel
    ``"_try_next"`` to indicate that the next credential should be tried.
    """
    client = TelegramClient(session_str, api_id, api_hash, receive_updates=False)
    network_attempts = 0

    while True:  # retry loop for OSError
        try:
            await client.connect()

            if not await client.is_user_authorized():
                LOGGER.debug("Session not authorised (api_id=%d)", api_id)
                return "invalid"

            # --- send /start and wait for SpamBot reply ---
            try:
                sent_msg = await client.send_message(_SPAMBOT_USERNAME, "/start")
                sent_id = getattr(sent_msg, "id", 0)
            except FloodWaitError as exc:
                if exc.seconds <= _MAX_FLOOD_WAIT_SECONDS:
                    LOGGER.debug(
                        "FloodWait %ds on sendMessage; waiting (api_id=%d)",
                        exc.seconds,
                        api_id,
                    )
                    await asyncio.sleep(exc.seconds + 1)
                    sent_msg = await client.send_message(_SPAMBOT_USERNAME, "/start")
                    sent_id = getattr(sent_msg, "id", 0)
                else:
                    LOGGER.warning(
                        "FloodWait %ds too long to wait (api_id=%d); inconclusive",
                        exc.seconds,
                        api_id,
                    )
                    return "inconclusive"

            reply = await _wait_for_spambot_reply(client, sent_id, timeout)
            if reply is None:
                LOGGER.warning(
                    "@SpamBot did not reply within %ds; result inconclusive", timeout
                )
                return "inconclusive"

            return _parse_spambot_reply(reply)

        except ApiIdInvalidError:
            LOGGER.debug("ApiIdInvalid for api_id=%d; trying next credential", api_id)
            return "_try_next"

        except AuthKeyDuplicatedError:
            # The auth_key was invalidated by Telegram (concurrent login from
            # another location). This is a property of the SESSION, not the
            # API credential – rotating credentials will not help.
            LOGGER.debug("AuthKeyDuplicated – session invalidated by Telegram")
            return "invalid"

        except (AuthKeyError, AuthKeyUnregisteredError):
            LOGGER.debug("Auth key missing or unregistered – session expired")
            return "invalid"

        except FloodWaitError as exc:
            # Raised during connect/is_user_authorized (less common).
            if exc.seconds <= _MAX_FLOOD_WAIT_SECONDS:
                LOGGER.debug(
                    "FloodWait %ds on connect/auth; waiting (api_id=%d)",
                    exc.seconds,
                    api_id,
                )
                await asyncio.sleep(exc.seconds + 1)
                continue
            LOGGER.warning(
                "FloodWait %ds on connect (api_id=%d); inconclusive",
                exc.seconds,
                api_id,
            )
            return "inconclusive"

        except (UserDeactivatedError, UserDeactivatedBanError):
            # Account was self-deleted or auto-purged by Telegram.
            LOGGER.debug("Account deactivated")
            return "banned"

        except PhoneNumberBannedError:
            # Account permanently banned for ToS violations.
            LOGGER.debug("Account permanently banned (PhoneNumberBanned)")
            return "banned"

        except SessionPasswordNeededError:
            # The session was authorised before 2FA was enabled.  The account
            # itself is active and reachable – we just cannot call SpamBot.
            # Report as ``active`` (optimistic): the session works, and no
            # spam restriction prevented the connection.
            LOGGER.debug("Session requires 2FA password; reporting as active")
            return "active"

        except OSError as exc:
            network_attempts += 1
            if network_attempts <= _MAX_NETWORK_RETRIES:
                delay = _NETWORK_BACKOFF_BASE**network_attempts
                LOGGER.debug(
                    "OSError on attempt %d/%d (api_id=%d): %s; retrying in %ds",
                    network_attempts,
                    _MAX_NETWORK_RETRIES,
                    api_id,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            LOGGER.debug(
                "OSError after %d retries (api_id=%d); inconclusive",
                network_attempts,
                api_id,
            )
            return "inconclusive"

        finally:
            with suppress(Exception):
                await client.disconnect()


async def _wait_for_spambot_reply(
    client: Any,
    sent_id: int,
    timeout: int,
) -> str | None:
    """
    Poll @SpamBot's message history for a reply to message *sent_id*.

    Polls every second for up to *timeout* seconds. Returns the message text
    of the first incoming (not msg.out) message with id >= sent_id.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            messages = await client.get_messages(_SPAMBOT_USERNAME, limit=5)
            for msg in messages:
                is_incoming = not getattr(msg, "out", True)
                msg_id = getattr(msg, "id", 0)
                msg_text = getattr(msg, "message", None)
                if is_incoming and msg_id >= sent_id and msg_text:
                    return msg_text
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Error fetching SpamBot messages: %s", exc)
        await asyncio.sleep(1)
    return None


def _parse_spambot_reply(text: str) -> SpamStatus:
    """
    Classify @SpamBot reply as ``active`` or ``frozen``.

    Clean-account phrases are checked first (more specific).  If neither clean
    nor spam phrases match we return ``frozen`` as a safe default – it is
    better to falsely flag a clean account than to miss a restricted one.
    """
    lower = text.lower()
    for phrase in _CLEAN_KEYWORDS:
        if phrase.lower() in lower:
            return "active"
    for phrase in _SPAM_KEYWORDS:
        if phrase.lower() in lower:
            return "frozen"
    LOGGER.debug("Unrecognised @SpamBot reply (%.80r); defaulting to frozen", text)
    return "frozen"
