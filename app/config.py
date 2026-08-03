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
    spambot_timeout: int = Field(default=15, ge=5, le=60)
    # Optional 32-byte url-safe base64 key for encrypting user proxy passwords
    proxy_encryption_key: str = ""
    # Optional proxy URL for Bot connection (e.g., http://127.0.0.1:10809 or socks5://...)
    bot_proxy: str = ""
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
    custom_emoji_merge: str = ""
    custom_emoji_unlock: str = ""
    custom_emoji_reset: str = ""
    custom_emoji_refresh: str = ""
    custom_emoji_view: str = ""
    custom_emoji_edit: str = ""
    custom_emoji_add: str = ""
    custom_emoji_message: str = ""
    custom_emoji_ban: str = ""
    custom_emoji_unban: str = ""
    custom_emoji_flag_en: str = ""
    custom_emoji_flag_fa: str = ""
    custom_emoji_flag_ru: str = ""
    custom_emoji_flag_ar: str = ""
    custom_emoji_flag_zh: str = ""
    custom_emoji_flag_uz: str = ""
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
