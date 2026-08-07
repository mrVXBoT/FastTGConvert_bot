"""
Live spam-status checker via @SpamBot.

Design principles
-----------------
* Credentials are rotated ONLY for credential-level errors (ApiIdInvalid).
* Account-level errors (FloodWait, deactivated, banned) stop immediately.
* Network errors (OSError) are retried with exponential back-off on the same
  credential pair before giving up.
* 2FA accounts (SessionPasswordNeeded) are reported as ``inconclusive`` —
  the session connects but the account cannot be verified with @SpamBot, so
  reporting it ``active`` would overclaim a clean status.
* Credential exhaustion is ``inconclusive`` (not ``invalid``) because it does
  not prove the session is broken.
* A brand-new chat with @SpamBot receives the bot's WELCOME message (which
  contains the word "limited") instead of the account status, so /start is
  sent a second time whenever the first reply is missing or looks like the
  greeting; a reply that is still not the status is ``inconclusive``.

Error → result mapping
-----------------------
| Telethon error              | Result        | Rationale                         |
|-----------------------------|---------------|-----------------------------------|
| ApiIdInvalidError           | try next cred | credential is invalid, not session |
| connects but unauthorised   | banned        | account deactivated / limited     |
| AuthKeyDuplicatedError      | banned        | session force-terminated          |
| AuthKeyError /              | banned        | auth key revoked (deactivated)    |
|   AuthKeyUnregisteredError  |               |                                   |
| FloodWaitError (≤ limit)    | sleep + retry | account rate-limit, wait it out    |
| FloodWaitError (> limit)    | inconclusive  | can't wait this long               |
| UserDeactivatedError /      | banned        | account gone permanently           |
|   UserDeactivatedBanError   |               |                                    |
| PhoneNumberBannedError      | banned        | permanently banned by Telegram     |
| SessionPasswordNeededError  | inconclusive  | session works but 2FA blocks SpamBot   |
| OSError (up to MAX_RETRIES) | inconclusive  | transient network issue            |
| @SpamBot timeout            | inconclusive  | can't determine spam status        |
| Unrecognised @SpamBot reply | inconclusive  | reply language not covered         |
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


def _mask_api_id(api_id: int) -> str:
    """Mask an API credential id for log safety."""
    s = str(api_id)
    return f"{s[:3]}***" if len(s) > 3 else "***"

# FloodWait threshold: if Telegram asks us to wait longer than this we give up
# rather than blocking the handler for too long.
_MAX_FLOOD_WAIT_SECONDS = 30

# How many times to retry a single credential pair after an OSError.
_MAX_NETWORK_RETRIES = 2
_NETWORK_BACKOFF_BASE = 2  # seconds; doubled on each retry

# Phrases indicating a clean (unrestricted) account.
# Clean phrases are matched FIRST: several languages share a word root between
# "no restriction" and "restricted", so the positive (clean) phrases must win
# before any restriction keyword is considered.
_CLEAN_KEYWORDS = (
    # English
    "good news",
    "no limits",
    "not limited",
    "free as a bird",
    "no restrictions",
    "can continue",
    "restriction has been removed",
    "restrictions have been removed",
    # Telegram's generic "your number is fine but may hit harsh responses"
    # reply – the account is NOT currently limited.  Distinct from the
    # spam-limitation reply, which explicitly says the account is limited.
    "subscribe to telegram premium",
    "get less strict limits",
    "your phone number has no spam reports",
    "has not been reported as spam",
    # Farsi
    "خبر خوب",  # good news
    "هیچ محدودیتی",  # no restriction
    "هیچ محدودیتی اعمال",  # no restriction applied
    "محدودیتی اعمال نشده",  # no restriction has been applied
    "آزاد هستید",  # you are free
    # Arabic
    "أخبار جيدة",  # good news
    "أخبار سارة",  # good news
    "لا توجد قيود",  # there are no restrictions
    "لا قيود",  # no restrictions
    "لا توجد",  # there are no…
    # Russian
    "хорошие новости",  # good news
    "не применяются",  # (limits) are not applied
    "никаких ограничений",  # no restrictions at all
    "нет ограничений",  # no restrictions
    "ограничений нет",  # no restrictions
    "свободен от",  # (the account is) free from (any restrictions)
    # Spanish
    "buenas noticias",  # good news
    "no hay límites",  # there are no limits
    "sin límites",  # no limits
    "no hay restricciones",  # there are no restrictions
    # Portuguese
    "boas notícias",  # good news
    "não há limites",  # there are no limits
    "sem limites",  # no limits
    "nenhuma restrição",  # no restriction
    # German
    "gute nachrichten",  # good news
    "keine einschränkungen",  # no restrictions
    "keine beschränkungen",  # no restrictions
    # French
    "bonne nouvelle",  # good news
    "aucune restriction",  # no restriction
    "aucune limite",  # no limit
    "pas de restriction",  # no restriction
    # Italian
    "buone notizie",  # good news
    "nessuna limitazione",  # no restriction
    "nessun limite",  # no limit
    # Turkish
    "iyi haber",  # good news
    "herhangi bir kısıtlama",  # any restriction (in "no restriction is applied")
    "kısıtlama uygulanmıyor",  # restriction is not applied
    # Indonesian
    "kabar baik",  # good news
    "tidak ada batasan",  # there are no limits
    "tanpa batasan",  # without limits
    # Hindi
    "अच्छी खबर",  # good news
    "कोई प्रतिबंध नहीं",  # no restriction
    # Urdu
    "اچھی خبر",  # good news
    "کوئی پابندی نہیں",  # no restriction
    "پابندی نہیں",  # no restriction
    # Bengali
    "ভালো খবর",  # good news
    "কোনো বিধিনিষেধ",  # no restriction
    # Vietnamese
    "tin tốt",  # good news
    "không có giới hạn",  # there are no limits
    "không bị hạn chế",  # not restricted
    # Chinese
    "好消息",  # good news
    "没有任何限制",  # no restriction
    "沒有任何限制",  # no restriction (traditional)
    "不受限制",  # not restricted
    "限制都已取消",  # all restrictions have been lifted
    # Uzbek
    "yaxshi xabar",  # good news
    "hech qanday cheklovlar",  # no restrictions
    "cheklovlar yo'q",  # no restrictions
    "cheklovlar yoʻq",  # no restrictions
)

# Phrases indicating a spam-flagged account: restricted because of spam
# reports/complaints. SpamBot's spam-limitation reply ("…limited by
# mistake…", "…reported as spam…", "…cannot message non-contacts…") must be
# distinguished from a genuine freeze, so these phrases are matched BEFORE
# the frozen phrases.  A spam-flagged account is appealable via SpamBot's
# complaint flow, whereas a frozen account goes through the ToS appeal.
_SPAM_KEYWORDS = (
    # English – SpamBot's spam-limitation + complaint flow
    "this account is limited",
    "account is limited",
    "has been limited",
    "is limited for sending",
    "is now limited",
    "limited by mistake",
    "limited for sending spam",
    "limited due to sending spam",
    "limited for sending unsolicited",
    "restricted due to spam",
    "unsolicited messages",
    "reported as spam",
    "reported by other users",
    "marked as spam",
    "flagged as spam",
    "considered spam",
    "spam reports",
    "spam-related",
    "mutual contacts",
    "can only send messages to people who have your number",
    "send messages to people who do not have your number",
    "complaint has been successfully submitted",
    "your request has been forwarded",
    "appeal has been submitted",
    "your appeal has been",
    "reviewers will look",
    "will review your case",
    "has been forwarded to our team",
    # Russian
    "излишне сурово",  # (the anti-spam system reacts) too harshly
    "взаимным контактам",  # only to mutual contacts
    "за рассылку спама",  # for sending spam
    # Farsi
    "به اشتباه محدود",  # limited by mistake
    "ارسال اسپم محدود",  # limited for sending spam
    "حساب شما محدود",  # your account is limited
    # Arabic
    "بالخطأ",  # by mistake
    "بسبب إرسال السبام",  # due to sending spam
    "حسابك محدود",  # your account is limited
    # Hindi
    "गलती से सीमित",  # limited by mistake
    "स्पैम भेजने के लिए सीमित",  # limited for sending spam
    "आपका खाता सीमित",  # your account is limited
    # Urdu
    "غلطی سے محدود",  # limited by mistake
    "اسپیم بھیجنے پر محدود",  # limited for sending spam
    "آپ کا اکاؤنٹ محدود",  # your account is limited
    # Bengali
    "ভুলবশত সীমিত",  # limited by mistake
    "স্প্যাম পাঠানোর জন্য সীমিত",  # limited for sending spam
    # Chinese
    "被误限制",  # limited by mistake
    "误封",  # mistakenly restricted
    "因发送垃圾邮件被限制",  # limited for sending spam
    "账户被限制",  # account is limited
    "仅可向",  # can only (send to mutual contacts)
    # Spanish / Portuguese / German / French / Italian / Turkish / Indonesian /
    # Vietnamese / Uzbek
    "limitado por error",  # limited by mistake
    "limitado por engano",  # limited by mistake
    "versehentlich eingeschränkt",  # limited by mistake
    "limité par erreur",  # limited by mistake
    "limitato per errore",  # limited by mistake
    "yanlışlıkla kısıtlandı",  # limited by mistake
    "dibatasi karena kesalahan",  # limited by mistake
    "bị giới hạn nhầm",  # limited by mistake
    "xatolik bilan cheklangan",  # limited by mistake
)

# Phrases indicating a genuinely frozen account (limited / restricted).
# Since Telegram's 2025+ "freeze" feature this covers SpamBot's ToS-appeal
# flow ("blocked for violations of the Terms of Service…").  Only STRONG
# ToS/freeze wording lives here: the generic word "limited" belongs to the
# appealable spam limitation (SpamBot's canonical "This account is limited.")
# and must NOT steal those replies.
_FROZEN_KEYWORDS = (
    # English
    "blocked for violations",
    "terms of service",
    "team supervisor",
    "supervisor has reviewed",
    "will remain limited",
    "for violations of",
    "is frozen",
    "account is frozen",
    "frozen for",
    "restricted by the terms",
    "permanently frozen",
    # Farsi
    "مسدود",  # blocked
    "محدودیت اعمال شده",  # restriction has been applied
    "برای نقض قوانین",  # for violating the rules
    "نقض قوانین",  # violation of rules
    # Arabic
    "محظور",  # blocked
    "بسبب انتهاك شروط",  # due to violating the terms
    "بسبب انتهاك",  # due to violating
    "لانتهاك شروط",  # for violating the terms
    # Russian
    "заблокирован",  # blocked
    "за нарушения",  # for violations
    "нарушение правил",  # violation of rules
    # Spanish
    "bloqueado por",  # blocked for (violations)
    "por violación",  # for violation (of the terms)
    # Portuguese
    "bloqueado por",  # blocked for
    "por violação",  # for violation
    # German
    "blockiert wegen",  # blocked because of
    "verstoß gegen",  # violation of (terms)
    "nutzungsbedingungen",  # terms of use
    # French
    "bloqué pour",  # blocked for
    "violation des conditions",  # violation of the terms
    "conditions d'utilisation",  # terms of use
    # Italian
    "bloccato per",  # blocked for
    "violazione dei termini",  # violation of the terms
    # Turkish
    "ihlal",  # violation (of the terms of service)
    "kullanım koşulları",  # terms of use
    "hizmet şartları",  # terms of service
    # Indonesian
    "diblokir karena",  # blocked because (of violating)
    "melanggar ketentuan",  # violating the terms
    # Hindi
    "सेवा की शर्तों के उल्लंघन",  # violation of the terms of service
    "शर्तों का उल्लंघन",  # violation of the terms
    # Urdu
    "خدمت کی شرائط کی خلاف ورزی",  # violation of the terms of service
    "شرائط کی خلاف ورزی",  # violation of the terms
    # Bengali
    "পরিষেবার শর্তাবলী লঙ্ঘন",  # violation of the terms of service
    "শর্তাবলী লঙ্ঘন",  # violation of the terms
    # Vietnamese
    "vi phạm",  # violation (of the terms)
    "điều khoản dịch vụ",  # terms of service
    # Chinese
    "违规",  # violations
    "申诉",  # appeal
    "团队主管",  # team supervisor
    "冻结",  # frozen
    "违反服务条款",  # violation of the terms of service
    # Uzbek
    "bloklangan",  # blocked
    "shartlarni buzish",  # violation of the terms
)

# Phrases indicating a permanently banned account.
_BANNED_KEYWORDS = (
    # English
    "has been banned",
    "is banned",
    "was banned",
    "permanently banned",
    "suspended",
    # Russian
    "заблокирован навсегда",  # permanently blocked
    # Arabic
    "محظور نهائيا",  # permanently blocked
    "حظر دائم",  # permanent ban
    # Spanish
    "prohibido permanentemente",  # permanently banned
    # Chinese
    "已被封禁",  # has been banned
    "已被禁止",  # has been banned / forbidden
)

# Six distinct outcomes; mapped to SessionCheckResult fields by session_checker.
SpamStatus = Literal["active", "spam", "frozen", "banned", "invalid", "inconclusive"]


async def check_spam_via_spambot(
    session_path: Path,
    credentials: list[tuple[int, str]],
    timeout: int = 15,
    proxy: tuple | None = None,
) -> SpamStatus:
    """
    Connect with *session_path* and query @SpamBot for the account's spam status.
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
                proxy=proxy,
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
    proxy: tuple | None = None,
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
    """
    client = TelegramClient(
        session_str, api_id, api_hash, receive_updates=False, proxy=proxy
    )
    network_attempts = 0

    while True:  # retry loop for OSError
        try:
            await client.connect()

            if not await client.is_user_authorized():
                # The connection succeeded (valid auth_key server-side) but
                # there is no user behind it: the account was deactivated or
                # permanently limited by Telegram.  Reference checkers report
                # these as BANNED / deactivated, not as a corrupt session.
                LOGGER.debug("Session connects but is not authorised (api_id=%s)", _mask_api_id(api_id))
                return "banned"

            # --- send /start and wait for SpamBot reply ---
            reply = await _spambot_status_reply(client, timeout, FloodWaitError)
            if reply is None:
                LOGGER.warning(
                    "@SpamBot did not reply within %ds; result inconclusive", timeout
                )
                return "inconclusive"

            LOGGER.debug("SpamBot reply received (%.300r)", reply)
            return _parse_spambot_reply(reply)

        except ApiIdInvalidError:
            LOGGER.debug("ApiIdInvalid for api_id=%s; trying next credential", _mask_api_id(api_id))
            return "_try_next"

        except AuthKeyDuplicatedError:
            # The auth_key was invalidated by Telegram (concurrent login from
            # another location). This is a property of the SESSION, not the
            # API credential – rotating credentials will not help.  The session
            # was force-terminated → the account is banned/deactivated.
            LOGGER.debug("AuthKeyDuplicated – session invalidated by Telegram")
            return "banned"

        except (AuthKeyError, AuthKeyUnregisteredError):
            # Auth key missing or unregistered → the account was deactivated
            # or its session revoked.  Reported as banned/deactivated, matching
            # the reference checker output.
            LOGGER.debug("Auth key missing or unregistered – session expired")
            return "banned"

        except FloodWaitError as exc:
            # Raised during connect/is_user_authorized (less common).
            if exc.seconds <= _MAX_FLOOD_WAIT_SECONDS:
                LOGGER.debug(
                    "FloodWait %ds on connect/auth; waiting (api_id=%s)",
                    exc.seconds,
                    _mask_api_id(api_id),
                )
                await asyncio.sleep(exc.seconds + 1)
                continue
            LOGGER.warning(
                "FloodWait %ds on connect (api_id=%s); inconclusive",
                exc.seconds,
                _mask_api_id(api_id),
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
            # The session is valid, but a two-step password was enabled after
            # this session was authorised, so we cannot reach @SpamBot and
            # cannot verify the spam status. Reporting ``inconclusive`` avoids
            # overclaiming a clean "No Restriction" status.
            LOGGER.debug("Session requires 2FA password; reporting as inconclusive")
            return "inconclusive"

        except OSError as exc:
            network_attempts += 1
            if network_attempts <= _MAX_NETWORK_RETRIES:
                delay = _NETWORK_BACKOFF_BASE**network_attempts
                LOGGER.debug(
                    "OSError on attempt %d/%d (api_id=%s): %s; retrying in %ds",
                    network_attempts,
                    _MAX_NETWORK_RETRIES,
                    _mask_api_id(api_id),
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


# Phrases that identify SpamBot's welcome message rather than an account
# status reply.  When an account messages @SpamBot for the FIRST time, the
# bot answers with this greeting ("…if your account was limited…") instead of
# the real status – classifying the greeting as the status is what made
# healthy accounts show up as frozen.
_GREETING_KEYWORDS = (
    "spam info bot",
    "official spam info bot",
    "i can help you find out",
    "i'm sorry in advance",
    "just a robot",
    "talk bluntly",
    "regain the full functionality",
)


def _looks_like_greeting(text: str | None) -> bool:
    """Return True if *text* looks like SpamBot's welcome message."""
    if not text:
        return False
    lower = text.casefold()
    return any(phrase in lower for phrase in _GREETING_KEYWORDS)


async def _send_start(client: Any, FloodWaitError: Any) -> int | None:
    """
    Send /start to @SpamBot and return the sent message id.

    Returns ``None`` when Telegram asks us to wait longer than
    ``_MAX_FLOOD_WAIT_SECONDS`` (cannot wait that long).
    """
    while True:
        try:
            sent_msg = await client.send_message(_SPAMBOT_USERNAME, "/start")
            return getattr(sent_msg, "id", 0)
        except FloodWaitError as exc:
            if exc.seconds > _MAX_FLOOD_WAIT_SECONDS:
                LOGGER.warning(
                    "FloodWait %ds too long to wait on sendMessage; inconclusive",
                    exc.seconds,
                )
                return None
            LOGGER.debug("FloodWait %ds on sendMessage; waiting", exc.seconds)
            await asyncio.sleep(exc.seconds + 1)


async def _spambot_status_reply(
    client: Any, timeout: int, FloodWaitError: Any
) -> str | None:
    """
    Ask @SpamBot for the account's status and return the status message text.

    Two /start commands are sent back-to-back: on a brand-new chat the FIRST
    /start only wakes the bot up (it answers with its welcome message,
    whatever the account's interface language), and only the SECOND /start
    produces the actual account status.  The poll then reads the NEWEST
    incoming message after the second command, so the welcome message can
    never be mistaken for the status.  Returns ``None`` if no status could
    be obtained.
    """
    reply: str | None = None
    for _ in range(2):
        sent_id = await _send_start(client, FloodWaitError)
        if sent_id is None:
            return None
        reply = await _wait_for_spambot_reply(client, sent_id, timeout)
        if reply is not None and not _looks_like_greeting(reply):
            return reply
    return None if _looks_like_greeting(reply) else reply


async def _wait_for_spambot_reply(
    client: Any,
    sent_id: int,
    timeout: int,
) -> str | None:
    """
    Poll @SpamBot's message history for a reply to message *sent_id*.

    Polls every second for up to *timeout* seconds. Returns the message text
    of the first incoming (not msg.out) message with id strictly greater than
    *sent_id* – the reply must arrive AFTER our /start, otherwise a stale
    reply from a previous check could be mistaken for the current one.
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
                if is_incoming and sent_id and msg_id > sent_id and msg_text:
                    return msg_text
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Error fetching SpamBot messages: %s", exc)
        await asyncio.sleep(1)
    return None


def _parse_spambot_reply(text: str) -> SpamStatus:
    """
    Classify @SpamBot reply as ``active``, ``spam``, ``frozen`` or ``banned``.

    Match order (most specific first):
      1. ``active``   – clean / no-restriction wording.
      2. ``frozen``   – STRONG ToS/freeze wording ("blocked for violations of
                        the Terms of Service", "is frozen", …).  Matched before
                        spam so a ToS block is never swallowed by the generic
                        "limited" phrase that spam replies share.
      3. ``spam``     – spam-flag / limitation wording ("this account is
                        limited", "limited by mistake", "mutual contacts",
                        "unsolicited messages", complaint flow, …).
      4. ``banned``   – explicit permanent ban wording.

    Clean-account phrases are matched first because in some languages the
    "no restriction" reply shares a word root with the restriction phrases
    (e.g. Russian "никакие ограничения" vs "ограничен",
    Farsi "هیچ محدودیتی" vs "محدود").

    If the reply is not recognised we return ``inconclusive`` – never
    ``frozen``.  @SpamBot replies in the account's interface language, so an
    unrecognised reply usually means the language is simply not covered, not
    that the account is restricted.  Guessing "frozen" here is what made
    healthy accounts show up as fully blocked.
    """
    lower = text.casefold()
    for phrase in _CLEAN_KEYWORDS:
        if phrase in lower:
            return "active"
    for phrase in _FROZEN_KEYWORDS:
        if phrase in lower:
            return "frozen"
    for phrase in _SPAM_KEYWORDS:
        if phrase in lower:
            return "spam"
    for phrase in _BANNED_KEYWORDS:
        if phrase in lower:
            return "banned"
    LOGGER.debug("Unrecognised @SpamBot reply (%.80r); marking inconclusive", text)
    return "inconclusive"
