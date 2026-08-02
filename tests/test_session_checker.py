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

from app.services.spam import SpamStatus, _parse_spambot_reply
from app.session_checker import (
    _classify_session_file,
    _collect_offline_statuses,
    _summarize,
    check_sessions,
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
            checked=5, active=2, frozen=1, banned=1, invalid=1, inconclusive=0
        )
        assert r.checked == 5

    def test_violated_invariant_raises(self) -> None:
        with pytest.raises(ValueError, match="checked"):
            SessionCheckResult(
                checked=3, active=2, frozen=1, banned=1, invalid=0, inconclusive=0
            )

    def test_default_banned_inconclusive_zero(self) -> None:
        r = SessionCheckResult(checked=1, active=1, frozen=0, invalid=0)
        assert r.banned == 0
        assert r.inconclusive == 0


# --------------------------------------------------------------------------- #
# _parse_spambot_reply                                                         #
# --------------------------------------------------------------------------- #


class TestParseSpamBotReply:
    @pytest.mark.parametrize(
        "text",
        [
            "Good news, no limits are applied to your account.",
            "No limits are currently applied.",
            "You can continue using Telegram.",
            "You are not limited.",
        ],
    )
    def test_clean_account_returns_active(self, text: str) -> None:
        assert _parse_spambot_reply(text) == "active"

    @pytest.mark.parametrize(
        "text",
        [
            "Your account has been limited.",
            "This account is restricted due to spam.",
            "Your account was limited for sending spam.",
        ],
    )
    def test_spam_restricted_returns_frozen(self, text: str) -> None:
        assert _parse_spambot_reply(text) == "frozen"

    def test_unrecognised_reply_defaults_to_frozen(self) -> None:
        # Safe default: don't falsely report a restricted account as clean.
        assert _parse_spambot_reply("Something completely unknown.") == "frozen"


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
        statuses: list = ["active", "frozen", "banned", "invalid", "inconclusive"]
        r = _summarize(statuses)
        assert r.checked == 5
        assert r.active == 1
        assert r.frozen == 1
        assert r.banned == 1
        assert r.invalid == 1
        assert r.inconclusive == 1

    def test_invariant_holds(self) -> None:
        statuses: list = [
            "active",
            "active",
            "frozen",
            "banned",
            "invalid",
            "inconclusive",
        ]
        r = _summarize(statuses)
        assert r.checked == r.active + r.frozen + r.banned + r.invalid + r.inconclusive

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
        assert result == SessionCheckResult(checked=1, active=1, frozen=0, invalid=0)

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
        assert result.active == 1
        assert result.frozen == 1

    async def test_invariant_always_holds(self, tmp_path: Path) -> None:
        p = tmp_path / "any.session"
        _make_session(p)
        result = await check_sessions(p)
        total = (
            result.active
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

    async def test_spam_account_becomes_frozen(self, tmp_path: Path) -> None:
        p = tmp_path / "spam.session"
        _make_session(p, auth_key=b"k" * 256)
        with patch(
            "app.session_checker._live_status", new=AsyncMock(return_value="frozen")
        ):
            result = await check_sessions(p, credentials=[(12345, "abc")])
        assert result.frozen == 1 and result.active == 0

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

    async def test_live_check_exception_falls_back_to_active(
        self, tmp_path: Path
    ) -> None:
        p = tmp_path / "ok.session"
        _make_session(p, auth_key=b"k" * 256)
        with patch(
            "app.session_checker._live_status",
            new=AsyncMock(side_effect=RuntimeError("unexpected crash")),
        ):
            result = await check_sessions(p, credentials=[(12345, "abc")])
        assert result.active == 1

    async def test_zip_all_buckets_via_live(self, tmp_path: Path) -> None:
        """ZIP with 3 sessions → active, banned, inconclusive via mocked live check."""
        sessions: list[bytes] = []
        for i in range(3):
            s = tmp_path / f"s{i}.session"
            _make_session(s, auth_key=b"k" * 256)
            sessions.append(s.read_bytes())

        archive = tmp_path / "multi.zip"
        _make_zip(archive, {f"s{i}.session": d for i, d in enumerate(sessions)})

        returns: list[SpamStatus] = ["active", "banned", "inconclusive"]
        with patch(
            "app.session_checker._live_status",
            new=AsyncMock(side_effect=returns),
        ):
            result = await check_sessions(archive, credentials=[(1, "x")])

        assert result.checked == 3
        assert result.active == 1
        assert result.banned == 1
        assert result.inconclusive == 1
        assert result.frozen == 0
        assert result.invalid == 0
