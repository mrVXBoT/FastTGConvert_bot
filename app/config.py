from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: str = Field(min_length=20)
    database_url: str = "sqlite:///data/bot.db"
    storage_dir: Path = Path("data/storage")
    max_upload_mb: int = Field(default=20, ge=1, le=2000)
    retention_minutes: int = Field(default=60, ge=5, le=10080)
    required_channels: str = ""
    # Telegram username, t.me URL, tg:// user URL, or numeric user ID.
    support_id: str = ""
    admin_id: int = 0
    # Telegram API credentials – comma-separated list of  id:hash  pairs.
    # Example: API_CREDENTIALS=12345:abc,67890:def
    # Obtained from https://my.telegram.org  (keep this secret!)
    api_credentials: str = ""
    # Seconds to wait for @SpamBot reply before timing out
    spambot_timeout: int = Field(default=15, ge=1, le=60)
    # Contacts check job tuning: concurrent sessions, per-session timeout and
    # max FloodWait seconds honoured before skipping a credential.
    contacts_check_concurrency: int = Field(default=3, ge=1, le=2000)
    contacts_check_timeout: int = Field(default=30, ge=5, le=300)
    contacts_flood_ceiling: int = Field(default=5, ge=0, le=30)
    # Account-age check tuning: how many sessions are probed in parallel
    # (each needs one TelegramClient with a fresh temp session file).
    account_age_concurrency: int = Field(default=100, ge=1, le=2000)
    # Profile-setup prefetch: how many session profiles are fetched in
    # parallel during the initial scan before the interactive editor opens.
    profile_setup_concurrency: int = Field(default=50, ge=1, le=2000)
    # Split job tuning: how many sessions are live-verified in parallel.
    split_concurrency: int = Field(default=10, ge=1, le=20)
    # Clean chat job tuning: concurrent sessions and max FloodWait seconds to
    # honour per dialog before skipping it.
    clean_chat_concurrency: int = Field(default=5, ge=1, le=20)
    clean_chat_flood_ceiling: int = Field(default=30, ge=0, le=300)
    # How many chats are deleted concurrently within one session. Sequential
    # per-chat deletion is very slow for accounts with many dialogs; a small
    # concurrent batch overlaps the network RPC latency.
    clean_chat_delete_concurrency: int = Field(default=5, ge=1, le=20)
    # Optional 32-byte url-safe base64 key for encrypting user proxy passwords
    proxy_encryption_key: str = ""
    # Optional proxy URL for Bot connection (e.g., http://127.0.0.1:10809 or socks5://...)
    bot_proxy: str = ""
    # Optional API keys for on-chain auto payment verification (empty = public endpoints)
    tron_api_key: str = ""
    bsc_api_key: str = ""
    # Comma-separated BSC RPC node URLs (e.g. https://rpc.ankr names / bsc-dataseed).
    # When set, BEP20 detection runs keyless via eth_getLogs on these nodes
    # instead of requiring a paid Etherscan V2 plan.
    bsc_rpc_urls: str = ""
    # How often to scan for confirmed auto payments (seconds)
    payment_check_interval_seconds: int = Field(default=15, ge=5, le=300)
    # Validity window for auto payment orders (hours)
    payment_order_hours: int = Field(default=2, ge=1, le=72)
    # Extra seconds after expiry that a pending order is still accepted for a
    # confirmed on-chain transfer (protects payments made at the edge of the window).
    payment_expiry_grace_seconds: int = Field(default=1200, ge=0, le=86400)
    # Custom Telegram Emoji IDs for Telegram Premium themes
    custom_emoji_vip: str = ""
    custom_emoji_users: str = ""
    custom_emoji_admin: str = ""
    custom_emoji_stats: str = ""
    custom_emoji_settings: str = ""
    custom_emoji_success: str = ""
    custom_emoji_delete: str = ""
    custom_emoji_back: str = ""
    custom_emoji_broadcast: str = ""
    custom_emoji_support: str = ""
    custom_emoji_force_join: str = ""
    custom_emoji_search: str = ""
    custom_emoji_security: str = ""
    custom_emoji_cancel: str = ""
    custom_emoji_convert: str = ""
    custom_emoji_spam: str = ""
    custom_emoji_otp: str = ""
    custom_emoji_contacts: str = ""
    custom_emoji_export: str = ""
    custom_emoji_split: str = ""
    custom_emoji_split_country: str = "5211157547645421280"
    custom_emoji_split_quantity: str = "5210729536974503652"
    custom_emoji_merge: str = ""
    custom_emoji_merge_multi_type: str = "6298486951657867390"
    custom_emoji_merge_json_tdata: str = "6296504553667823627"
    custom_emoji_unlock: str = ""
    custom_emoji_reset: str = ""
    custom_emoji_refresh: str = ""
    custom_emoji_view: str = ""
    custom_emoji_edit: str = ""
    custom_emoji_add: str = ""
    custom_emoji_message: str = ""
    custom_emoji_photo: str = ""
    custom_emoji_loading: str = ""
    # Comma-separated custom emoji IDs forming a decorative divider strip,
    # e.g. CUSTOM_EMOJI_DIVIDER=id1,id2,id3  (rendered side by side).
    custom_emoji_divider: str = ""
    custom_emoji_active: str = ""
    custom_emoji_frozen: str = ""
    custom_emoji_banned: str = ""
    custom_emoji_inconclusive: str = ""
    custom_emoji_checked: str = ""
    custom_emoji_invalid: str = "5821328845420106343"
    custom_emoji_total: str = "5821421565174092291"
    custom_emoji_converted: str = "5940635490645449104"
    custom_emoji_failed: str = "5940804914220372462"
    custom_emoji_phone: str = ""
    custom_emoji_username: str = ""
    custom_emoji_calls: str = ""
    custom_emoji_voice: str = ""
    custom_emoji_world: str = ""
    custom_emoji_link: str = ""
    custom_emoji_gift: str = ""
    custom_emoji_trophy: str = ""
    custom_emoji_medal: str = ""
    custom_emoji_otp_code: str = ""
    custom_emoji_session: str = ""
    custom_emoji_check: str = ""
    custom_emoji_skip: str = ""
    custom_emoji_contact_checked: str = ""
    custom_emoji_contact_ok: str = ""
    custom_emoji_contact_error: str = ""
    custom_emoji_ban: str = ""
    custom_emoji_unban: str = ""
    custom_emoji_flag_en: str = ""
    custom_emoji_flag_fa: str = ""
    custom_emoji_flag_ru: str = ""
    custom_emoji_flag_ar: str = ""
    custom_emoji_flag_zh: str = ""
    custom_emoji_flag_uz: str = ""
    # Clean Chat category + action icons
    custom_emoji_dm: str = ""
    custom_emoji_bot: str = ""
    custom_emoji_group: str = ""
    custom_emoji_channel: str = ""
    custom_emoji_confirm: str = ""
    # Prometheus HTTP metrics exporter configuration
    metrics_enabled: bool = True
    metrics_host: str = "127.0.0.1"
    metrics_port: int = Field(default=8080, ge=1000, le=65535)
    metrics_auth_token: str = ""

    @property
    def api_credential_list(self) -> list[tuple[int, str]]:
        """Return parsed (api_id, api_hash) pairs from the env string."""
        result: list[tuple[int, str]] = []
        for entry in self.api_credentials.split(","):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(":", 1)
            if len(parts) != 2:
                continue
            try:
                result.append((int(parts[0].strip()), parts[1].strip()))
            except ValueError:
                continue
        return result

    @property
    def required_channel_list(self) -> tuple[str, ...]:
        return tuple(
            channel.strip()
            for channel in self.required_channels.split(",")
            if channel.strip()
        )

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
