"""
Tests for app.session_checker and app.services.spam

Covers:
  - Offline structural classification (_classify_session_file)
  - Extension guard (_collect_offline_statuses)
  - ZIP safety and multi-member processing
  - _summarize correctness and invariant
  - check_sessions offline (no credentials)
  - check_sessions live (mocked _live_status)
  - _parse_spambot_reply keyword matching
  - SessionCheckResult invariant enforcement
"""

from __future__ import annotations

import io
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.spam import (
    SpamStatus,
    _looks_like_greeting,
    _parse_spambot_reply,
    _spambot_status_reply,
)
from app.session_checker import (
    SessionCheckEntry,
    SessionProgress,
    _classify_session_file,
    _collect_offline_statuses,
    _detect_session_phone,
    _summarize,
    build_status_zips,
    check_sessions,
    check_sessions_detailed,
)
from app.session_results import SessionCheckResult

# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _make_session(path: Path, *, auth_key: bytes | None = b"x" * 256) -> None:
    """Create a minimal Telethon-style .session SQLite file."""
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE sessions "
            "(dc_id INTEGER, server_address TEXT, port INTEGER, "
            "auth_key BLOB, takeout_id INTEGER)"
        )
        if auth_key is not None:
            conn.execute(
                "INSERT INTO sessions VALUES (2, '149.154.167.51', 443, ?, NULL)",
                (auth_key,),
            )


def _make_zip(
    dest: Path,
    members: dict[str, bytes],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
) -> None:
    with zipfile.ZipFile(dest, "w", compression=compression) as zf:
        for name, data in members.items():
            zf.writestr(name, data)


# --------------------------------------------------------------------------- #
# SessionCheckResult invariant                                                 #
# --------------------------------------------------------------------------- #


class TestSessionCheckResultInvariant:
    def test_valid_result(self) -> None:
        r = SessionCheckResult(
            checked=5,
            active=2,
            spam=0,
            frozen=1,
            banned=1,
            invalid=1,
            inconclusive=0,
        )
        assert r.checked == 5

    def test_violated_invariant_raises(self) -> None:
        with pytest.raises(ValueError, match="checked"):
            SessionCheckResult(
                checked=3, active=2, frozen=1, banned=1, invalid=0, inconclusive=0
            )

    def test_default_banned_inconclusive_spam_zero(self) -> None:
        r = SessionCheckResult(checked=1, active=1, frozen=0, invalid=0)
        assert r.banned == 0
        assert r.inconclusive == 0
        assert r.spam == 0


# --------------------------------------------------------------------------- #
# _parse_spambot_reply                                                         #
# --------------------------------------------------------------------------- #


class TestParseSpamBotReply:
    @pytest.mark.parametrize(
        "text",
        [
            "Good news, no limits are applied to your account.",
            (
                "Good news, no limits are currently applied to your account. "
                "You're free as a bird!"
            ),
            "No limits are currently applied.",
            "You can continue using Telegram.",
            "You are not limited.",
            # Farsi clean reply – must NOT match the Farsi "محدود" spam keyword
            "خبر خوب، هیچ محدودیتی در حال حاضر برای حساب شما اعمال نشده است.",
            # Russian clean reply – must NOT match the "ограничен" spam keyword
            (
                "Хорошие новости, к вашему аккаунту в данный момент не применяются "
                "никакие ограничения."
            ),
            # Arabic clean reply
            "أخبار جيدة، لا توجد قيود على حسابك حالياً.",
            # Spanish / Portuguese / German / French
            "Buenas noticias, no hay límites aplicados a tu cuenta.",
            "Boas notícias, não há limites aplicados à sua conta.",
            "Gute Nachrichten, keine Einschränkungen sind auf Ihr Konto angewandt.",
            "Bonne nouvelle, aucune restriction n'est appliquée à votre compte.",
        ],
    )
    def test_clean_account_returns_active(self, text: str) -> None:
        assert _parse_spambot_reply(text) == "active"

    @pytest.mark.parametrize(
        "text",
        [
            "Your account has been limited.",
            "This account is restricted due to spam.",
        ],
    )
    def test_restricted_replies_are_spam_not_frozen(self, text: str) -> None:
        # A generic limitation (appealable via SpamBot) is SPAM, never the
        # ToS freeze.  This over-matching was what inflated the frozen bucket.
        assert _parse_spambot_reply(text) == "spam"

    @pytest.mark.parametrize(
        "text",
        [
            "К сожалению, этот номер телефона ограничен или заблокирован.",
            "عذراً، رقم الهاتف هذا محدود أو محظور.",
        ],
    )
    def test_blocked_phone_replies_are_frozen(self, text: str) -> None:
        # These explicitly mention the number being BLOCKED, a strong ToS/
        # freeze signal, so they remain frozen.
        assert _parse_spambot_reply(text) == "frozen"

    def test_phone_limited_or_banned_is_inconclusive(self) -> None:
        # "limited or banned" is genuinely ambiguous between the two buckets –
        # do not guess.
        assert (
            _parse_spambot_reply("Sorry, this phone number is limited or banned.")
            == "inconclusive"
        )

    @pytest.mark.parametrize(
        "text",
        [
            # Spam-flagged replies – the "limited by mistake" complaint flow.
            (
                "I'm very sorry, but your account was limited by mistake. You "
                "can submit a complaint to our moderators."
            ),
            (
                "Unfortunately, your account is now limited. You will not be "
                "able to send messages to people who do not have your number "
                "in their phone contacts."
            ),
            "Your account was limited for sending spam.",
            "Your account was flagged as spam by other users.",
            "Your actions were reported as spam.",
            # Farsi / Russian / Chinese spam-flagged replies
            "حساب شما به دلیل ارسال اسپم محدود شده است.",
            "К сожалению, иногда наша антиспам-система излишне сурово реагирует.",
            "您的账户被误限制。",
        ],
    )
    def test_spam_flagged_returns_spam(self, text: str) -> None:
        assert _parse_spambot_reply(text) == "spam"

    @pytest.mark.parametrize(
        "text",
        [
            (
                "Unfortunately, the phone number that is currently used to operate "
                "your account has been banned."
            ),
            "This phone number is banned.",
        ],
    )
    def test_banned_wording_returns_banned(self, text: str) -> None:
        assert _parse_spambot_reply(text) == "banned"

    def test_unrecognised_reply_is_inconclusive(self) -> None:
        # Never guess "frozen" for a reply we cannot read: @SpamBot answers in
        # the account's interface language, so an unrecognised reply does not
        # prove the account is restricted.
        assert _parse_spambot_reply("Something completely unknown.") == "inconclusive"


# --------------------------------------------------------------------------- #
# SpamBot welcome-message handling                                             #
# --------------------------------------------------------------------------- #


class TestSpamBotGreeting:
    WELCOME = (
        "Hello! I'm Telegram's official Spam Info Bot. I can help you find out "
        "if your account was limited. I'll also explain why this happens and "
        "what you can do to regain the full functionality. I'm sorry in advance "
        "if I have to talk bluntly sometimes. After all, I'm just a robot."
    )
    CLEAN_STATUS = (
        "Good news, no limits are currently applied to your account. "
        "You're free as a bird!"
    )
    LIMITED_STATUS = (
        "I'm very sorry that you had to contact me. Unfortunately, some actions "
        "can trigger a harsh response from our anti-spam systems. This is "
        "usually not your fault, but the actions were done from your account."
    )
    NUMBER_FLAG_STATUS = (
        "Unfortunately, some phone numbers may trigger a harsh response from our "
        "anti-spam systems. If you think this is the case with you, you can "
        "submit a complaint to our moderators or subscribe to Telegram Premium "
        "to get less strict limits."
    )

    def test_welcome_message_is_detected(self) -> None:
        # The welcome message must NOT be treated as an account status – it
        # literally contains the word "limited".  Upstream the greeting is
        # filtered out and /start sent again; if it ever reaches the parser it
        # must classify as inconclusive, never "frozen".
        assert _looks_like_greeting(self.WELCOME) is True
        assert _parse_spambot_reply(self.WELCOME) == "inconclusive"

    def test_status_replies_are_not_greetings(self) -> None:
        assert _looks_like_greeting(self.CLEAN_STATUS) is False
        assert _looks_like_greeting(self.LIMITED_STATUS) is False

    def test_number_flag_reply_is_active(self) -> None:
        # "some phone numbers may trigger a harsh response … subscribe to
        # Telegram Premium to get less strict limits" is SpamBot's generic
        # number-flag reply – it does NOT say the account is limited.  Live
        # ground truth (NoRestriction_29.zip) confirms these are CLEAN/active.
        assert _looks_like_greeting(self.NUMBER_FLAG_STATUS) is False
        assert _parse_spambot_reply(self.NUMBER_FLAG_STATUS) == "active"

    def test_real_clean_reply_is_active(self) -> None:
        # Captured verbatim from @SpamBot for the NoRestriction_29.zip set.
        # Shares the "harsh response / anti-spam systems" wording with the
        # genuinely-limited reply, but never says the account IS limited.
        clean = (
            "Unfortunately, some phone numbers may trigger a harsh response "
            "from our anti-spam systems. If you think this is the case with "
            "you, you can submit a complaint to our moderators or subscribe "
            "to Telegram Premium to get less strict limits."
        )
        assert _parse_spambot_reply(clean) == "active"

    def test_limited_by_mistake_reply_is_spam(self) -> None:
        # The genuinely spam-flagged reply ALSO mentions "anti-spam systems" –
        # but the explicit "limited by mistake" wording must be classified as
        # SPAM (spam-flagged, complaint flow), NOT as a freeze.
        limited = (
            "Hello +2347047848725!\n\nI'm very sorry that you had to contact me. "
            "Unfortunately, some actions can trigger a harsh response from our "
            "anti-spam systems. If you think your account was limited by mistake, "
            "you can submit a complaint to our moderators. While the account is "
            "limited, you will not be able to message non-contacts."
        )
        assert _parse_spambot_reply(limited) == "spam"

    @pytest.mark.asyncio
    async def test_fresh_chat_retries_start_and_gets_status(self) -> None:
        # First attempt's poll only finds the welcome message, the second attempt gets the real status.
        with (
            patch("app.services.spam._wait_for_spambot_reply") as fake_wait,
            patch("app.services.spam._send_start") as mock_send_start,
        ):
            mock_send_start.side_effect = [10, 20]
            fake_wait.side_effect = [self.WELCOME, self.CLEAN_STATUS]
            reply = await _spambot_status_reply(
                AsyncMock(), timeout=15, FloodWaitError=Exception
            )

        assert reply == self.CLEAN_STATUS
        assert mock_send_start.call_count == 2

    @pytest.mark.asyncio
    async def test_existing_chat_gets_status_after_double_start(self) -> None:
        # Returning account: the first /start already produces the status, so
        # the second /start's poll finds it immediately.
        with (
            patch("app.services.spam._send_start", new=AsyncMock(return_value=5)),
            patch(
                "app.services.spam._wait_for_spambot_reply",
                new=AsyncMock(return_value=self.CLEAN_STATUS),
            ),
        ):
            reply = await _spambot_status_reply(
                AsyncMock(), timeout=15, FloodWaitError=Exception
            )
        assert reply == self.CLEAN_STATUS

    @pytest.mark.asyncio
    async def test_only_welcome_messages_is_inconclusive(self) -> None:
        # If SpamBot keeps answering with the welcome message, we must not
        # guess a status.
        with (
            patch("app.services.spam._send_start", new=AsyncMock(return_value=5)),
            patch(
                "app.services.spam._wait_for_spambot_reply",
                new=AsyncMock(return_value=self.WELCOME),
            ),
        ):
            reply = await _spambot_status_reply(
                AsyncMock(), timeout=15, FloodWaitError=Exception
            )
        assert reply is None


# --------------------------------------------------------------------------- #
# _classify_session_file                                                       #
# --------------------------------------------------------------------------- #


class TestClassifySessionFile:
    def test_valid_with_auth_key(self, tmp_path: Path) -> None:
        p = tmp_path / "good.session"
        _make_session(p, auth_key=b"a" * 256)
        assert _classify_session_file(p) == "structurally_valid"

    def test_incomplete_when_auth_key_is_empty_bytes(self, tmp_path: Path) -> None:
        p = tmp_path / "empty_key.session"
        _make_session(p, auth_key=b"")
        assert _classify_session_file(p) == "incomplete"

    def test_incomplete_when_no_row(self, tmp_path: Path) -> None:
        p = tmp_path / "no_row.session"
        _make_session(p, auth_key=None)
        assert _classify_session_file(p) == "incomplete"

    def test_invalid_no_sessions_table(self, tmp_path: Path) -> None:
        p = tmp_path / "no_table.session"
        with sqlite3.connect(p) as conn:
            conn.execute("CREATE TABLE something (x INTEGER)")
        assert _classify_session_file(p) == "invalid"

    def test_invalid_corrupt_file(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.session"
        p.write_bytes(b"NOT A SQLITE FILE AT ALL !!!")
        assert _classify_session_file(p) == "invalid"

    def test_invalid_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.session"
        p.write_bytes(b"")
        assert _classify_session_file(p) == "invalid"

    def test_invalid_nonexistent_file(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.session"
        assert _classify_session_file(p) == "invalid"


# --------------------------------------------------------------------------- #
# _collect_offline_statuses – extension guard                                  #
# --------------------------------------------------------------------------- #


class TestExtensionGuard:
    def test_session_extension_accepted(self, tmp_path: Path) -> None:
        p = tmp_path / "valid.session"
        _make_session(p)
        assert _collect_offline_statuses(p) == ["structurally_valid"]

    def test_zip_extension_accepted(self, tmp_path: Path) -> None:
        sess = tmp_path / "inner.session"
        _make_session(sess)
        archive = tmp_path / "archive.zip"
        _make_zip(archive, {"inner.session": sess.read_bytes()})
        assert _collect_offline_statuses(archive) == ["structurally_valid"]

    @pytest.mark.parametrize("ext", [".txt", ".db", ".sqlite", ".bin", ""])
    def test_unsupported_extensions_rejected(self, tmp_path: Path, ext: str) -> None:
        p = tmp_path / f"file{ext}"
        p.write_bytes(b"data")
        assert _collect_offline_statuses(p) == ["invalid"]


# --------------------------------------------------------------------------- #
# _collect_offline_statuses – ZIP safety                                       #
# --------------------------------------------------------------------------- #


class TestZipProcessing:
    def test_zip_with_multiple_sessions(self, tmp_path: Path) -> None:
        sess_valid = tmp_path / "a.session"
        _make_session(sess_valid, auth_key=b"v" * 256)
        sess_incomplete = tmp_path / "b.session"
        _make_session(sess_incomplete, auth_key=None)
        archive = tmp_path / "batch.zip"
        _make_zip(
            archive,
            {
                "a.session": sess_valid.read_bytes(),
                "b.session": sess_incomplete.read_bytes(),
                "c.session": b"NOT SQLITE",
            },
        )
        statuses = _collect_offline_statuses(archive)
        assert sorted(statuses) == sorted(
            ["structurally_valid", "incomplete", "invalid"]
        )

    def test_zip_with_no_session_members(self, tmp_path: Path) -> None:
        archive = tmp_path / "nosess.zip"
        _make_zip(archive, {"readme.txt": b"hello"})
        assert _collect_offline_statuses(archive) == ["invalid"]

    def test_zip_slip_absolute_path_rejected(self, tmp_path: Path) -> None:
        archive = tmp_path / "slip.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(zipfile.ZipInfo("/etc/passwd.session"), b"data")
        archive.write_bytes(buf.getvalue())
        assert _collect_offline_statuses(archive) == ["invalid"]

    def test_zip_slip_dotdot_rejected(self, tmp_path: Path) -> None:
        archive = tmp_path / "slip2.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(zipfile.ZipInfo("../../evil.session"), b"data")
        archive.write_bytes(buf.getvalue())
        assert _collect_offline_statuses(archive) == ["invalid"]

    def test_too_many_members_rejected(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("app.session_checker._MAX_ZIP_MEMBERS", 2)
        archive = tmp_path / "big.zip"
        _make_zip(
            archive,
            {f"f{i}.session": b"x" for i in range(3)},
            compression=zipfile.ZIP_STORED,
        )
        assert _collect_offline_statuses(archive) == ["invalid"]

    def test_bad_zip_file(self, tmp_path: Path) -> None:
        archive = tmp_path / "bad.zip"
        archive.write_bytes(b"this is not a zip file")
        assert _collect_offline_statuses(archive) == ["invalid"]

    def test_one_bad_member_does_not_abort_rest(self, tmp_path: Path) -> None:
        good_sess = tmp_path / "good.session"
        _make_session(good_sess, auth_key=b"k" * 256)
        archive = tmp_path / "mixed.zip"
        _make_zip(
            archive, {"good.session": good_sess.read_bytes(), "bad.session": b"GBG"}
        )
        statuses = _collect_offline_statuses(archive)
        assert "structurally_valid" in statuses
        assert "invalid" in statuses
        assert len(statuses) == 2


# --------------------------------------------------------------------------- #
# _summarize                                                                   #
# --------------------------------------------------------------------------- #


class TestSummarize:
    def test_all_buckets(self) -> None:
        statuses: list = [
            "active",
            "spam",
            "frozen",
            "banned",
            "invalid",
            "inconclusive",
        ]
        r = _summarize(statuses)
        assert r.checked == 6
        assert r.active == 1
        assert r.spam == 1
        assert r.frozen == 1
        assert r.banned == 1
        assert r.invalid == 1
        assert r.inconclusive == 1

    def test_invariant_holds(self) -> None:
        statuses: list = [
            "active",
            "active",
            "spam",
            "frozen",
            "banned",
            "invalid",
            "inconclusive",
        ]
        r = _summarize(statuses)
        assert (
            r.checked
            == r.active + r.spam + r.frozen + r.banned + r.invalid + r.inconclusive
        )

    def test_empty_list(self) -> None:
        r = _summarize([])
        assert r == SessionCheckResult(checked=0, active=0, frozen=0, invalid=0)

    def test_summarize_triggers_dataclass_invariant(self) -> None:
        # _summarize should always produce a valid SessionCheckResult.
        r = _summarize(["active", "frozen", "invalid"])
        assert r.checked == 3


# --------------------------------------------------------------------------- #
# check_sessions – offline only (no credentials)                               #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestCheckSessionsOffline:
    async def test_single_valid_session(self, tmp_path: Path) -> None:
        p = tmp_path / "ok.session"
        _make_session(p, auth_key=b"z" * 256)
        result = await check_sessions(p)
        assert result == SessionCheckResult(
            checked=1, active=0, frozen=0, invalid=0, inconclusive=1
        )

    async def test_single_incomplete_session(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.session"
        _make_session(p, auth_key=None)
        result = await check_sessions(p)
        assert result == SessionCheckResult(checked=1, active=0, frozen=1, invalid=0)

    async def test_single_invalid_file(self, tmp_path: Path) -> None:
        p = tmp_path / "junk.session"
        p.write_bytes(b"not sqlite")
        result = await check_sessions(p)
        assert result == SessionCheckResult(checked=1, active=0, frozen=0, invalid=1)

    async def test_unsupported_extension(self, tmp_path: Path) -> None:
        p = tmp_path / "file.tdata"
        p.write_bytes(b"irrelevant")
        result = await check_sessions(p)
        assert result.invalid == 1 and result.checked == 1

    async def test_zip_mixed_offline(self, tmp_path: Path) -> None:
        valid = tmp_path / "v.session"
        _make_session(valid, auth_key=b"a" * 256)
        incomplete = tmp_path / "i.session"
        _make_session(incomplete, auth_key=None)
        archive = tmp_path / "test.zip"
        _make_zip(
            archive,
            {"v.session": valid.read_bytes(), "i.session": incomplete.read_bytes()},
        )
        result = await check_sessions(archive)
        assert result.checked == 2
        assert result.inconclusive == 1
        assert result.frozen == 1

    async def test_zip_reports_progress(self, tmp_path: Path) -> None:
        valid = tmp_path / "v.session"
        _make_session(valid, auth_key=b"a" * 256)
        incomplete = tmp_path / "i.session"
        _make_session(incomplete, auth_key=None)
        archive = tmp_path / "test.zip"
        _make_zip(
            archive,
            {"v.session": valid.read_bytes(), "i.session": incomplete.read_bytes()},
        )
        progress = SessionProgress()
        await check_sessions_detailed(
            archive, credentials=[(1, "h")], progress=progress
        )
        assert progress.total == 2
        assert progress.done == 2

    async def test_single_file_reports_progress(self, tmp_path: Path) -> None:
        p = tmp_path / "ok.session"
        _make_session(p, auth_key=b"z" * 256)
        progress = SessionProgress()
        await check_sessions_detailed(p, progress=progress)
        assert progress.total == 1
        assert progress.done == 1

    async def test_invariant_always_holds(self, tmp_path: Path) -> None:
        p = tmp_path / "any.session"
        _make_session(p)
        result = await check_sessions(p)
        total = (
            result.active
            + result.spam
            + result.frozen
            + result.banned
            + result.invalid
            + result.inconclusive
        )
        assert result.checked == total


# --------------------------------------------------------------------------- #
# check_sessions – with live spam check (mocked _live_status)                  #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestCheckSessionsLive:
    async def test_clean_account_becomes_active(self, tmp_path: Path) -> None:
        p = tmp_path / "ok.session"
        _make_session(p, auth_key=b"k" * 256)
        with patch(
            "app.session_checker._live_status", new=AsyncMock(return_value="active")
        ):
            result = await check_sessions(p, credentials=[(12345, "abc")])
        assert result.active == 1 and result.frozen == 0

    async def test_spam_flagged_account_becomes_spam(self, tmp_path: Path) -> None:
        p = tmp_path / "spam.session"
        _make_session(p, auth_key=b"k" * 256)
        with patch(
            "app.session_checker._live_status", new=AsyncMock(return_value="spam")
        ):
            result = await check_sessions(p, credentials=[(12345, "abc")])
        assert result.spam == 1 and result.frozen == 0 and result.active == 0

    async def test_frozen_account_becomes_frozen(self, tmp_path: Path) -> None:
        p = tmp_path / "frozen.session"
        _make_session(p, auth_key=b"k" * 256)
        with patch(
            "app.session_checker._live_status", new=AsyncMock(return_value="frozen")
        ):
            result = await check_sessions(p, credentials=[(12345, "abc")])
        assert result.frozen == 1 and result.spam == 0 and result.active == 0

    async def test_banned_account_becomes_banned(self, tmp_path: Path) -> None:
        p = tmp_path / "banned.session"
        _make_session(p, auth_key=b"k" * 256)
        with patch(
            "app.session_checker._live_status", new=AsyncMock(return_value="banned")
        ):
            result = await check_sessions(p, credentials=[(12345, "abc")])
        assert result.banned == 1
        assert result.frozen == 0
        assert result.invalid == 0

    async def test_auth_failure_becomes_invalid(self, tmp_path: Path) -> None:
        p = tmp_path / "expired.session"
        _make_session(p, auth_key=b"k" * 256)
        with patch(
            "app.session_checker._live_status", new=AsyncMock(return_value="invalid")
        ):
            result = await check_sessions(p, credentials=[(12345, "abc")])
        assert result.invalid == 1

    async def test_inconclusive_becomes_inconclusive(self, tmp_path: Path) -> None:
        p = tmp_path / "flood.session"
        _make_session(p, auth_key=b"k" * 256)
        with patch(
            "app.session_checker._live_status",
            new=AsyncMock(return_value="inconclusive"),
        ):
            result = await check_sessions(p, credentials=[(12345, "abc")])
        assert result.inconclusive == 1
        assert result.frozen == 0

    async def test_incomplete_session_skips_live_check(self, tmp_path: Path) -> None:
        p = tmp_path / "incomplete.session"
        _make_session(p, auth_key=None)
        with patch(
            "app.session_checker._live_status",
            new=AsyncMock(
                side_effect=AssertionError("must not be called for incomplete")
            ),
        ):
            result = await check_sessions(p, credentials=[(12345, "abc")])
        assert result.frozen == 1

    async def test_live_check_exception_falls_back_to_inconclusive(
        self, tmp_path: Path
    ) -> None:
        p = tmp_path / "ok.session"
        _make_session(p, auth_key=b"k" * 256)
        with patch(
            "app.session_checker._live_status",
            new=AsyncMock(side_effect=RuntimeError("unexpected crash")),
        ):
            result = await check_sessions(p, credentials=[(12345, "abc")])
        assert result.inconclusive == 1

    async def test_zip_all_buckets_via_live(self, tmp_path: Path) -> None:
        """ZIP with 4 sessions → active, spam, banned, inconclusive via mocked live check."""
        sessions: list[bytes] = []
        for i in range(4):
            s = tmp_path / f"s{i}.session"
            _make_session(s, auth_key=b"k" * 256)
            sessions.append(s.read_bytes())

        archive = tmp_path / "multi.zip"
        _make_zip(archive, {f"s{i}.session": d for i, d in enumerate(sessions)})

        returns: list[SpamStatus] = ["active", "spam", "banned", "inconclusive"]
        with patch(
            "app.session_checker._live_status",
            new=AsyncMock(side_effect=returns),
        ):
            result = await check_sessions(archive, credentials=[(1, "x")])

        assert result.checked == 4
        assert result.active == 1
        assert result.spam == 1
        assert result.banned == 1
        assert result.inconclusive == 1
        assert result.frozen == 0
        assert result.invalid == 0


# --------------------------------------------------------------------------- #
# check_sessions_detailed + build_status_zips                                  #
# --------------------------------------------------------------------------- #


class TestStatusZipSeparation:
    async def test_detailed_zip_preserves_member_names(self, tmp_path: Path) -> None:
        valid = tmp_path / "2348100756846.session"
        _make_session(valid, auth_key=b"a" * 256)
        archive = tmp_path / "test.zip"
        _make_zip(archive, {"2348100756846.session": valid.read_bytes()})

        with patch(
            "app.session_checker._live_status",
            new=AsyncMock(return_value="active"),
        ):
            result, entries = await check_sessions_detailed(
                archive, credentials=[(12345, "h")]
            )
            assert result.active == 1
            assert entries == [SessionCheckEntry("2348100756846.session", "active")]

    async def test_detailed_single_file(self, tmp_path: Path) -> None:
        p = tmp_path / "ok.session"
        _make_session(p, auth_key=b"z" * 256)
        with patch(
            "app.session_checker._live_status",
            new=AsyncMock(return_value="active"),
        ):
            result, entries = await check_sessions_detailed(
                p, credentials=[(12345, "h")]
            )
            assert result.active == 1
            assert entries == [SessionCheckEntry("ok.session", "active")]

    def test_build_zips_groups_by_status_with_siblings(self, tmp_path: Path) -> None:
        # 9 active + 1 spam + 1 frozen, each .session with a sibling .json →
        # three zips: No_Restriction_9.zip, Spam_1.zip, Frozen_1.zip, with
        # siblings kept together.
        archive = tmp_path / "input.zip"
        members: dict[str, bytes] = {}
        entries: list[SessionCheckEntry] = []
        for i in range(9):
            name = f"234810000000{i}.session"
            members[name] = b"active-session"
            members[name.replace(".session", ".json")] = b"{}"
            entries.append(SessionCheckEntry(name, "active"))
        members["+2347047848725.session"] = b"spam-session"
        members["+2347047848725.json"] = b"{}"
        entries.append(SessionCheckEntry("+2347047848725.session", "spam"))
        members["+2347055555555.session"] = b"frozen-session"
        members["+2347055555555.json"] = b"{}"
        entries.append(SessionCheckEntry("+2347055555555.session", "frozen"))
        _make_zip(archive, members)

        out = tmp_path / "out"
        out.mkdir()
        archives = build_status_zips(archive, entries, out)

        assert sorted(p.name for p, _, _ in archives) == [
            "Frozen_1.zip",
            "No_Restriction_9.zip",
            "Spam_1.zip",
        ]
        by_name = {p.name: (p, status, count) for p, status, count in archives}
        assert by_name["No_Restriction_9.zip"][1:] == ("active", 9)
        assert by_name["Spam_1.zip"][1:] == ("spam", 1)
        assert by_name["Frozen_1.zip"][1:] == ("frozen", 1)

        with zipfile.ZipFile(by_name["No_Restriction_9.zip"][0]) as zf:
            names = set(zf.namelist())
            assert len(names) == 18
            assert "2348100000000.session" in names
            assert "2348100000000.json" in names
            assert "+2347047848725.session" not in names
        with zipfile.ZipFile(by_name["Spam_1.zip"][0]) as zf:
            names = set(zf.namelist())
            assert names == {"+2347047848725.session", "+2347047848725.json"}
        with zipfile.ZipFile(by_name["Frozen_1.zip"][0]) as zf:
            names = set(zf.namelist())
            assert names == {"+2347055555555.session", "+2347055555555.json"}

    def test_build_zips_single_session_upload_keeps_original_name(
        self, tmp_path: Path
    ) -> None:
        # The downloaded temp file has a UUID-ish name; the user's original
        # upload name must be restored inside the status ZIP.
        p = tmp_path / "787c6fda56944d6a9385340e6a98b82f.session"
        p.write_bytes(b"session-data")
        entries = [SessionCheckEntry(p.name, "frozen")]
        out = tmp_path / "out"
        out.mkdir()

        archives = build_status_zips(
            p, entries, out, original_name="_12167587713.session"
        )

        assert len(archives) == 1
        zip_path, status, count = archives[0]
        assert status == "frozen" and count == 1
        with zipfile.ZipFile(zip_path) as zf:
            assert zf.namelist() == ["_12167587713.session"]
            assert zf.read("_12167587713.session") == b"session-data"

    def test_build_zips_single_session_upload_uses_path_name_without_original(
        self, tmp_path: Path
    ) -> None:
        p = tmp_path / "acc.session"
        p.write_bytes(b"session-data")
        out = tmp_path / "out"
        out.mkdir()
        entries = [SessionCheckEntry("acc.session", "frozen")]

        archives = build_status_zips(p, entries, out)

        assert len(archives) == 1
        zip_path, status, count = archives[0]
        assert status == "frozen" and count == 1
        assert zip_path.name == "Frozen_1.zip"
        with zipfile.ZipFile(zip_path) as zf:
            assert zf.namelist() == ["acc.session"]
            assert zf.read("acc.session") == b"session-data"

    def test_build_zips_skips_empty_buckets(self, tmp_path: Path) -> None:
        archive = tmp_path / "input.zip"
        _make_zip(archive, {"a.session": b"data"})
        out = tmp_path / "out"
        out.mkdir()

        archives = build_status_zips(
            archive, [SessionCheckEntry("a.session", "invalid")], out
        )

        assert len(archives) == 1
        assert archives[0][1] == "invalid"
        assert archives[0][2] == 1


class TestDetectSessionPhone:
    def test_telethon_entities_table(self, tmp_path: Path) -> None:
        p = tmp_path / "a.session"
        with sqlite3.connect(p) as conn:
            conn.execute("CREATE TABLE entities (id INTEGER, phone TEXT)")
            conn.execute("INSERT INTO entities VALUES (777000, '+12167587713')")
        assert _detect_session_phone(p) == "12167587713"

    def test_pyrogram_peers_table(self, tmp_path: Path) -> None:
        p = tmp_path / "b.session"
        with sqlite3.connect(p) as conn:
            conn.execute("CREATE TABLE peers (id INTEGER, phone TEXT)")
            conn.execute("INSERT INTO peers VALUES (1, '+2347047848725')")
        assert _detect_session_phone(p) == "2347047848725"

    def test_strips_non_digits(self, tmp_path: Path) -> None:
        p = tmp_path / "c.session"
        with sqlite3.connect(p) as conn:
            conn.execute("CREATE TABLE users (id INTEGER, phone TEXT)")
            conn.execute("INSERT INTO users VALUES (1, '1216 758-7713')")
        assert _detect_session_phone(p) == "12167587713"

    def test_no_phone_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "d.session"
        with sqlite3.connect(p) as conn:
            conn.execute("CREATE TABLE entities (id INTEGER, phone TEXT)")
            conn.execute("INSERT INTO entities VALUES (1, NULL)")
            conn.execute("INSERT INTO entities VALUES (2, '')")
        assert _detect_session_phone(p) is None

    def test_corrupt_file_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "e.session"
        p.write_bytes(b"not a db")
        assert _detect_session_phone(p) is None


class TestBuildZipsPhoneNaming:
    def test_single_upload_named_by_phone(self, tmp_path: Path) -> None:
        # Even when the original upload name was mangled by safe_filename,
        # the status ZIP member must be named by the session's phone number.
        p = tmp_path / "787c6fda56944d6a9385340e6a98b82f.session"
        p.write_bytes(b"session-data")
        out = tmp_path / "out"
        out.mkdir()
        entries = [SessionCheckEntry(p.name, "frozen", phone="12167587713")]

        archives = build_status_zips(p, entries, out)

        assert len(archives) == 1
        zip_path, status, count = archives[0]
        assert status == "frozen" and count == 1
        assert zip_path.name == "Frozen_1.zip"
        with zipfile.ZipFile(zip_path) as zf:
            assert zf.namelist() == ["+12167587713.session"]
            assert zf.read("+12167587713.session") == b"session-data"

    def test_zip_members_renamed_by_phone(self, tmp_path: Path) -> None:
        archive = tmp_path / "input.zip"
        _make_zip(
            archive,
            {
                "_12167587713.session": b"active-session",
                "_12167587713.json": b"{}",
            },
        )
        out = tmp_path / "out"
        out.mkdir()
        entries = [
            SessionCheckEntry("_12167587713.session", "active", phone="12167587713")
        ]

        archives = build_status_zips(archive, entries, out)

        assert len(archives) == 1
        zip_path, status, count = archives[0]
        assert status == "active" and count == 1
        assert zip_path.name == "No_Restriction_1.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            assert names == {"+12167587713.session", "+12167587713.json"}
            assert "_12167587713.session" not in names
