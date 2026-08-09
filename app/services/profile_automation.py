from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import aiohttp
import phonenumbers
from faker import Faker

from app.services.profile_setup import update_account_profile

LOGGER = logging.getLogger(__name__)

DEFAULT_LOCALE: Final = "en_US"
DEFAULT_NAT: Final = "US"

# ISO 3166-1 alpha-2 region codes (derived from the account phone number)
# mapped to a Faker locale with real local names, surnames and bios.
REGION_LOCALES: Final[dict[str, str]] = {
    "US": "en_US",
    "GB": "en_GB",
    "GG": "en_GB",
    "JE": "en_GB",
    "IM": "en_GB",
    "CA": "en_CA",
    "AU": "en_AU",
    "NZ": "en_AU",
    "IE": "en_GB",
    "IN": "en_IN",
    "ZA": "en_ZA",
    "DE": "de_DE",
    "AT": "de_DE",
    "CH": "de_DE",
    "FR": "fr_FR",
    "BE": "fr_FR",
    "IT": "it_IT",
    "ES": "es_ES",
    "MX": "es_MX",
    "AR": "es_ES",
    "CL": "es_ES",
    "CO": "es_ES",
    "PE": "es_ES",
    "VE": "es_ES",
    "EC": "es_ES",
    "BO": "es_ES",
    "UY": "es_ES",
    "PY": "es_ES",
    "CR": "es_ES",
    "PA": "es_ES",
    "DO": "es_ES",
    "GT": "es_ES",
    "HN": "es_ES",
    "SV": "es_ES",
    "NI": "es_ES",
    "BR": "pt_BR",
    "PT": "pt_PT",
    "RU": "ru_RU",
    "BY": "ru_RU",
    "UA": "uk_UA",
    "KZ": "ru_RU",
    "MN": "ru_RU",
    "KG": "ru_RU",
    "TR": "tr_TR",
    "AZ": "az_AZ",
    "UZ": "uz_UZ",
    "AM": "hy_AM",
    "GE": "ka_GE",
    "GR": "el_GR",
    "BG": "bg_BG",
    "RO": "ro_RO",
    "HU": "hu_HU",
    "PL": "pl_PL",
    "CZ": "cs_CZ",
    "SK": "sk_SK",
    "RS": "hr_HR",
    "HR": "hr_HR",
    "BA": "hr_HR",
    "SI": "hr_HR",
    "MK": "mk_MK",
    "AL": "sq_AL",
    "NL": "nl_NL",
    "SE": "sv_SE",
    "NO": "no_NO",
    "DK": "da_DK",
    "FI": "fi_FI",
    "IS": "sv_SE",
    "LT": "cs_CZ",
    "LV": "cs_CZ",
    "EE": "fi_FI",
    "IL": "he_IL",
    "IR": "fa_IR",
    "AF": "fa_IR",
    "PK": "hi_IN",
    "BD": "bn_BD",
    "NP": "ne_NP",
    "LK": "hi_IN",
    "TH": "th_TH",
    "VN": "vi_VN",
    "ID": "id_ID",
    "MY": "id_ID",
    "PH": "tl_PH",
    "SG": "en_GB",
    "HK": "zh_CN",
    "TW": "zh_TW",
    "CN": "zh_CN",
    "JP": "ja_JP",
    "KR": "ko_KR",
    "SA": "ar_SA",
    "AE": "ar_AE",
    "EG": "ar_EG",
    "QA": "ar_SA",
    "KW": "ar_SA",
    "BH": "ar_SA",
    "OM": "ar_SA",
    "JO": "ar_SA",
    "LB": "ar_SA",
    "IQ": "ar_SA",
    "YE": "ar_SA",
    "SY": "ar_SA",
    "PS": "ar_SA",
    "MA": "ar_EG",
    "TN": "ar_EG",
    "DZ": "ar_EG",
    "LY": "ar_EG",
    "SD": "ar_EG",
    "MR": "ar_EG",
}

# randomuser.me nationality codes for real, country-matched portrait photos.
REGION_NAT: Final[dict[str, str]] = {
    "US": "US",
    "GB": "GB",
    "CA": "CA",
    "AU": "AU",
    "NZ": "NZ",
    "IE": "IE",
    "BR": "BR",
    "FR": "FR",
    "DE": "DE",
    "CH": "CH",
    "ES": "ES",
    "FI": "FI",
    "NL": "NL",
    "NO": "NO",
    "DK": "DK",
    "TR": "TR",
    "UA": "UA",
    "IN": "IN",
    "IR": "IR",
    "RS": "RS",
    "MX": "MX",
    "HR": "HR",
}

PHOTO_API_URL: Final = "https://randomuser.me/api/"
MIN_PHOTO_BYTES: Final = 1024
JPEG_MAGIC: Final = b"\xff\xd8\xff"

# Telegram refuses profile photos smaller than 160x160 (PHOTO_INVALID_DIMENSIONS);
# randomuser.me serves 128x128 portraits, so upscale before upload.
MIN_PROFILE_PHOTO_SIZE: Final = 320


def _ensure_profile_photo_size(photo_bytes: bytes) -> bytes | None:
    """Upscale too-small JPEGs so Telegram accepts them as profile photos."""
    try:
        from PIL import Image  # type: ignore[import-untyped]

        with Image.open(io.BytesIO(photo_bytes)) as img:
            if img.width >= MIN_PROFILE_PHOTO_SIZE and img.height >= MIN_PROFILE_PHOTO_SIZE:
                return photo_bytes
            scale = max(
                MIN_PROFILE_PHOTO_SIZE / img.width,
                MIN_PROFILE_PHOTO_SIZE / img.height,
            )
            resized = img.resize(
                (round(img.width * scale), round(img.height * scale)),
                Image.LANCZOS,
            )
            if resized.mode != "RGB":
                resized = resized.convert("RGB")
            out = io.BytesIO()
            resized.save(out, format="JPEG", quality=95)
            return out.getvalue()
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Profile photo resize failed: %s", exc)
        return photo_bytes

USERNAME_RE: Final = re.compile(r"^[a-zA-Z0-9_]+$")
MIN_USERNAME_LEN: Final = 5
MAX_USERNAME_LEN: Final = 32


@dataclass(frozen=True)
class ProfileDraft:
    first_name: str
    last_name: str
    username: str
    about: str
    gender: str
    locale: str
    region: str


def _region_for_phone(phone: str) -> str:
    try:
        parsed = phonenumbers.parse(phone, None)
        return phonenumbers.region_code_for_number(parsed) or ""
    except phonenumbers.NumberParseException:
        return ""


def country_locale(phone: str) -> str:
    return REGION_LOCALES.get(_region_for_phone(phone), DEFAULT_LOCALE)


def country_nat(phone: str) -> str:
    return REGION_NAT.get(_region_for_phone(phone), DEFAULT_NAT)


def _slugify(value: str) -> str:
    ascii_only = (
        value.encode("ascii", errors="ignore").decode("ascii").strip().lower()
    )
    slug = re.sub(r"[^a-z0-9_]", "", ascii_only)
    return slug.strip("_")


def make_unique_username(
    first_name: str, last_name: str, used: set[str]
) -> str:
    """Build a Telegram-valid, batch-unique username from a real name."""
    base = _slugify(first_name) + _slugify(last_name)
    if len(base) < MIN_USERNAME_LEN:
        base = base.ljust(MIN_USERNAME_LEN, "x")
    base = base[: MAX_USERNAME_LEN - 3]

    counter = 0
    while True:
        suffix = f"{counter:02d}" if counter else ""
        candidate = base + suffix
        counter += 1
        if len(candidate) < MIN_USERNAME_LEN:
            candidate = f"u{candidate}"
        candidate = candidate[:MAX_USERNAME_LEN].strip("_")
        while candidate and candidate[0].isdigit():
            candidate = f"u{candidate}"
        candidate = candidate[:MAX_USERNAME_LEN]
        if (
            USERNAME_RE.match(candidate)
            and MIN_USERNAME_LEN <= len(candidate) <= MAX_USERNAME_LEN
            and candidate not in used
        ):
            used.add(candidate)
            return candidate


def _build_about(fake: Faker) -> str:
    try:
        about = fake.job()
    except (AttributeError, ValueError):
        about = ""
    if not about:
        about = fake.sentence(nb_words=4)
    about = re.sub(r"\s+", " ", about).strip(" .")
    return about[:64]


def generate_profile_draft(phone: str, used_usernames: set[str]) -> ProfileDraft:
    """Random real-looking identity matching the account's country."""
    locale = country_locale(phone)
    fake = Faker(locale)
    gender = "female" if fake.random_int(0, 1) else "male"
    first_name = fake.first_name_male() if gender == "male" else fake.first_name_female()
    last_name = fake.last_name()
    username = make_unique_username(first_name, last_name, used_usernames)
    about = _build_about(fake)
    return ProfileDraft(
        first_name=first_name,
        last_name=last_name,
        username=username,
        about=about,
        gender=gender,
        locale=locale,
        region=_region_for_phone(phone) or "XX",
    )


async def download_profile_photo(gender: str, nat: str) -> bytes | None:
    """Download a unique real portrait photo matching the country."""
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=25)
        ) as session:
            async with session.get(
                PHOTO_API_URL,
                params={"gender": gender, "nat": nat},
            ) as resp:
                if resp.status != 200:
                    return None
                payload = await resp.json()
            results = payload.get("results") or []
            if not results:
                return None
            photo_url = results[0].get("picture", {}).get("large")
            if not photo_url:
                return None
            async with session.get(photo_url) as photo_resp:
                if photo_resp.status != 200:
                    return None
                photo_bytes = await photo_resp.read()
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Profile photo download failed: %s", exc)
        return None
    if len(photo_bytes) < MIN_PHOTO_BYTES or not photo_bytes.startswith(JPEG_MAGIC):
        return None
    return _ensure_profile_photo_size(photo_bytes)


async def auto_apply_account_profile(
    session_file: Path,
    credentials: list[tuple[int, str]],
    draft: ProfileDraft,
    photo_bytes: bytes | None,
    photo_dir: Path,
) -> bool:
    """Apply a generated identity to one session (photo written as temp file)."""
    photo_path = None
    if photo_bytes:
        photo_path = photo_dir / f"avatar_{draft.username}.jpg"
        photo_path.write_bytes(photo_bytes)
    try:
        return await update_account_profile(
            session_file,
            credentials,
            first_name=draft.first_name,
            last_name=draft.last_name,
            username=draft.username,
            about=draft.about,
            photo_path=photo_path,
        )
    finally:
        if photo_path is not None:
            photo_path.unlink(missing_ok=True)
