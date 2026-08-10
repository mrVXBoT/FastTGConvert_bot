#!/usr/bin/env python3
"""Automated Telegram API Credential Creator.

Logs into my.telegram.org using session files, extracts or creates App API_ID and API_HASH,
and appends them to .env and created_api_credentials.txt.
"""

import asyncio
import logging
import re
import sys
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup
from telethon import TelegramClient

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.services.device_params import get_stable_device_params

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
LOGGER = logging.getLogger("create_apis")

MY_TG_SEND_PASS_URL = "https://my.telegram.org/auth/send_password"
MY_TG_LOGIN_URL = "https://my.telegram.org/auth/login"
MY_TG_APPS_URL = "https://my.telegram.org/apps"
MY_TG_CREATE_APP_URL = "https://my.telegram.org/apps/create"


async def fetch_telegram_web_code(client: TelegramClient, timeout: int = 15) -> str | None:
    """Fetch the latest web login code sent by Telegram official channel (777000)."""
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        try:
            async for msg in client.iter_messages(777000, limit=5):
                text = msg.text or ""
                # Web login code pattern (alphanumeric, 8-12 chars)
                match = re.search(r"\b([a-zA-Z0-9_-]{8,14})\b", text)
                if match:
                    code = match.group(1)
                    # Check if code is recent (sent within last 60 seconds)
                    if msg.date and (asyncio.get_event_loop().time() - msg.date.timestamp() < 120):
                        return code
                    return code
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Error reading messages from 777000: %s", exc)

        await asyncio.sleep(1.5)

    return None


async def create_api_for_session(
    session_file: Path,
    session_http: aiohttp.ClientSession,
    base_api_id: int,
    base_api_hash: str,
) -> tuple[int, str] | None:
    """Log into my.telegram.org via session and create/extract (api_id, api_hash)."""
    session_name = session_file.stem
    device_kwargs = get_stable_device_params(session_file)

    client = TelegramClient(
        str(session_file.with_suffix("")),
        base_api_id,
        base_api_hash,
        **device_kwargs,
    )

    try:
        await asyncio.wait_for(client.connect(), timeout=15)
        if not await client.is_user_authorized():
            LOGGER.warning("Session %s is not authorized. Skipping.", session_name)
            return None

        me = await client.get_me()
        phone = getattr(me, "phone", "") or ""
        if not phone:
            LOGGER.warning("Could not obtain phone number for %s", session_name)
            return None

        if not phone.startswith("+"):
            phone_formatted = f"+{phone}"
        else:
            phone_formatted = phone

        LOGGER.info("[%s] Requesting web login code for phone %s...", session_name, phone_formatted)

        # Step 1: Send password request to my.telegram.org
        async with session_http.post(
            MY_TG_SEND_PASS_URL, data={"phone": phone_formatted}
        ) as res:
            if res.status != 200:
                LOGGER.warning("[%s] Failed to send password to my.telegram.org: HTTP %d", session_name, res.status)
                return None
            data = await res.json()
            random_hash = data.get("random_hash")
            if not random_hash:
                LOGGER.warning("[%s] No random_hash returned from my.telegram.org", session_name)
                return None

        # Step 2: Receive code from Telegram app
        LOGGER.info("[%s] Waiting for login code from Telegram service channel...", session_name)
        web_code = await fetch_telegram_web_code(client, timeout=20)
        if not web_code:
            LOGGER.warning("[%s] Web login code not received in time", session_name)
            return None

        LOGGER.info("[%s] Received web code. Logging into my.telegram.org...", session_name)

        # Step 3: Login to my.telegram.org
        login_data = {
            "phone": phone_formatted,
            "random_hash": random_hash,
            "password": web_code,
        }
        async with session_http.post(MY_TG_LOGIN_URL, data=login_data) as res:
            res_text = await res.text()
            if "true" not in res_text.lower() and res.status != 200:
                LOGGER.warning("[%s] Login failed to my.telegram.org: %s", session_name, res_text[:100])
                return None

        # Step 4: GET /apps page
        async with session_http.get(MY_TG_APPS_URL) as res:
            html = await res.text()

        # Parse HTML for existing app
        api_id_match = re.search(r"<strong>API id:</strong>\s*<span>(\d+)</span>", html) or re.search(r'name="app_id"\s+value="(\d+)"', html)
        api_hash_match = re.search(r"<strong>API hash:</strong>\s*<span>([a-f0-9]{32})</span>", html) or re.search(r'name="app_hash"\s+value="([a-f0-9]{32})"', html)

        if api_id_match and api_hash_match:
            api_id = int(api_id_match.group(1))
            api_hash = api_hash_match.group(1)
            LOGGER.info("✅ [%s] Found existing App: API_ID=%d, API_HASH=%s", session_name, api_id, api_hash)
            return api_id, api_hash

        # Step 5: If no app exists, create a new app
        LOGGER.info("[%s] Creating new App on my.telegram.org...", session_name)
        soup = BeautifulSoup(html, "html.parser")
        hash_input = soup.find("input", {"name": "hash"})
        form_hash = hash_input.get("value", "") if hash_input else ""

        app_title = f"App_{session_name[:8]}"
        app_shortname = f"app_{session_name[:6]}"
        create_data = {
            "hash": form_hash,
            "app_title": app_title,
            "app_shortname": app_shortname,
            "app_url": "",
            "app_platform": "desktop",
            "app_desc": "",
        }

        async with session_http.post(MY_TG_CREATE_APP_URL, data=create_data) as res:
            create_html = await res.text()

        api_id_match = re.search(r"<strong>API id:</strong>\s*<span>(\d+)</span>", create_html) or re.search(r'name="app_id"\s+value="(\d+)"', create_html)
        api_hash_match = re.search(r"<strong>API hash:</strong>\s*<span>([a-f0-9]{32})</span>", create_html) or re.search(r'name="app_hash"\s+value="([a-f0-9]{32})"', create_html)

        if api_id_match and api_hash_match:
            api_id = int(api_id_match.group(1))
            api_hash = api_hash_match.group(1)
            LOGGER.info("✨ [%s] Successfully Created App: API_ID=%d, API_HASH=%s", session_name, api_id, api_hash)
            return api_id, api_hash

        LOGGER.warning("[%s] Failed to extract API credentials from create response", session_name)
        return None

    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("[%s] Error creating API credentials: %s", session_name, exc)
        return None
    finally:
        if client and client.is_connected():
            with asyncio.suppress(Exception):
                await client.disconnect()


async def main() -> None:
    settings = get_settings()
    creds = settings.api_credential_list
    if not creds:
        LOGGER.error("No base API credentials found in settings/env. Please set at least one API_CREDENTIALS.")
        return

    base_api_id, base_api_hash = creds[0]

    # Target directory for session files to use for creating API keys
    input_dir = PROJECT_ROOT / "data" / "api_creator_sessions"
    input_dir.mkdir(parents=True, exist_ok=True)

    session_files = list(input_dir.glob("*.session"))
    if not session_files:
        # Check current folder or desktop for zip/session files if data folder is empty
        LOGGER.warning(
            "No .session files found in %s\n"
            "Please place some working .session files into 'data/api_creator_sessions/' to create API keys!",
            input_dir,
        )
        return

    LOGGER.info("Found %d session files for API creation.", len(session_files))

    created_pairs: list[tuple[int, str]] = []
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

    async with aiohttp.ClientSession(headers=headers) as session_http:
        for sf in session_files:
            res = await create_api_for_session(sf, session_http, base_api_id, base_api_hash)
            if res:
                created_pairs.append(res)

    if created_pairs:
        LOGGER.info("🎉 Successfully obtained %d API credential pairs!", len(created_pairs))
        
        # Save to output file
        out_txt = PROJECT_ROOT / "created_api_credentials.txt"
        env_str = ",".join(f"{id_}:{hash_}" for id_, hash_ in created_pairs)
        
        with open(out_txt, "a", encoding="utf-8") as f:
            f.write("\n" + env_str + "\n")

        LOGGER.info("Saved pairs to %s", out_txt)
        LOGGER.info("Add the following string to your .env API_CREDENTIALS:\n%s", env_str)


if __name__ == "__main__":
    asyncio.run(main())
