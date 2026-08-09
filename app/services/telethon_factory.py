from __future__ import annotations

import logging
import shutil
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING

from app.services.device_params import get_stable_device_params

LOGGER = logging.getLogger(__name__)


if TYPE_CHECKING:
    from telethon import TelegramClient  # type: ignore[import-untyped]


@asynccontextmanager
async def create_telethon_client(
    session_file: Path,
    api_id: int,
    api_hash: str,
    *,
    proxy: tuple | None = None,
    receive_updates: bool = False,
    device_seed: str | Path | None = None,
    device_params: dict[str, str] | None = None,
) -> AsyncGenerator[TelegramClient, None]:
    """Factory context manager for Telethon client connections.

    Creates an isolated temporary copy of the session file, initializes TelegramClient
    with authentic device parameters and proxy configuration, connects, and guarantees
    clean client disconnection and temporary file cleanup.
    """
    try:
        from telethon import TelegramClient  # type: ignore[import-untyped]
    except ModuleNotFoundError as err:
        LOGGER.error("Telethon library is not installed: %s", err)
        raise RuntimeError("Telethon library is missing") from err

    device_kwargs = device_params or get_stable_device_params(device_seed or session_file)

    with tempfile.TemporaryDirectory(prefix="ftgc_client_") as tmp_dir:
        run_session = Path(tmp_dir) / "account.session"
        shutil.copy2(session_file, run_session)
        client_stem = str(run_session.with_suffix(""))

        client = TelegramClient(
            client_stem,
            api_id,
            api_hash,
            receive_updates=receive_updates,
            proxy=proxy,
            **device_kwargs,
        )

        try:
            await client.connect()
            yield client
        finally:
            with suppress(Exception):
                await client.disconnect()
