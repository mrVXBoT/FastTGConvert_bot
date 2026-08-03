"""tests/test_ui_design_system.py — Tests for UI Design System (Button Factory, EmojiRegistry, ButtonStyle)."""

from pathlib import Path

from aiogram.types import InlineKeyboardButton, MessageEntity

from app.db.models import SystemSetting
from app.db.session import build_engine, build_session_factory, create_schema
from app.ui import (
    Button,
    ButtonStyle,
    EmojiRegistry,
    create_custom_emoji_entity,
    format_text_with_custom_emojis,
)


def test_button_factory_style_generation() -> None:
    """Verify Button.create generates InlineKeyboardButton with proper style attributes."""
    btn_primary = Button.create("Settings", "nav:settings", style=ButtonStyle.PRIMARY)
    btn_success = Button.create("Buy VIP", "vip:buy", style=ButtonStyle.SUCCESS)
    btn_danger = Button.create("Delete User", "user:delete:123", style=ButtonStyle.DANGER)

    assert isinstance(btn_primary, InlineKeyboardButton)
    assert btn_primary.text == "Settings"
    assert btn_primary.callback_data == "nav:settings"
    assert btn_primary.style == "primary"

    assert btn_success.style == "success"
    assert btn_success.callback_data == "vip:buy"

    assert btn_danger.style == "danger"
    assert btn_danger.callback_data == "user:delete:123"


def test_emoji_fallback_and_custom_id() -> None:
    """Verify fallback unicode is used when custom_emoji_id is unset, and custom_id is attached when set."""
    EmojiRegistry.clear()

    # Test fallback unicode
    unicode_icon, custom_id = EmojiRegistry.resolve_icon("VIP")
    assert unicode_icon == "💎"
    assert custom_id is None

    btn_fallback = Button.create("VIP Access", "vip:info", emoji_key="VIP", style=ButtonStyle.SUCCESS)
    assert btn_fallback.text == "💎 VIP Access"
    assert btn_fallback.icon_custom_emoji_id is None

    # Test custom emoji registration
    EmojiRegistry.set_custom_emoji("VIP", "1234567890987654321")
    unicode_icon, custom_id = EmojiRegistry.resolve_icon("VIP")
    assert unicode_icon == "💎"
    assert custom_id == "1234567890987654321"

    btn_custom = Button.create("VIP Access", "vip:info", emoji_key="VIP", style=ButtonStyle.SUCCESS)
    assert btn_custom.text == "VIP Access"  # Clean label without prepended unicode
    assert btn_custom.icon_custom_emoji_id == "1234567890987654321"

    EmojiRegistry.reset()


def test_db_emoji_override_and_missing_fallback(tmp_path: Path) -> None:
    """Verify DB system_settings (emoji:<KEY>) overrides registry, and missing DB emoji uses unicode fallback."""
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    create_schema(engine)
    session_factory = build_session_factory(engine)

    EmojiRegistry.clear()

    with session_factory() as session:
        # Add custom emoji setting to DB for VIP key
        db_setting = SystemSetting(key="emoji:VIP", value="5413351005779672594")
        session.add(db_setting)
        session.commit()

        # Load from DB into EmojiRegistry
        EmojiRegistry.load_from_db(session)

    # 1. DB-configured VIP emoji must use custom ID and clean text label
    btn_vip = Button.create("Buy VIP", "vip:buy", emoji_key="VIP", style=ButtonStyle.SUCCESS)
    assert btn_vip.text == "Buy VIP"
    assert btn_vip.icon_custom_emoji_id == "5413351005779672594"

    # 2. Missing DB ADMIN emoji must fallback to unicode and have no custom_emoji_id attached
    btn_admin = Button.create("Admin Panel", "adm:home", emoji_key="ADMIN", style=ButtonStyle.PRIMARY)
    assert btn_admin.text == "👮 Admin Panel"
    assert btn_admin.icon_custom_emoji_id is None

    engine.dispose()
    EmojiRegistry.reset()


def test_localized_button_creation() -> None:
    """Verify create_localized looks up dictionary keys properly."""
    EmojiRegistry.clear()
    loc_en = {"btn_stats": "Statistics", "btn_users": "Users Management"}
    loc_fa = {"btn_stats": "آمار", "btn_users": "مدیریت کاربران"}

    btn_en = Button.create_localized(loc_en, "btn_stats", "adm_nav:stats", style=ButtonStyle.PRIMARY, emoji_key="STATS")
    btn_fa = Button.create_localized(loc_fa, "btn_stats", "adm_nav:stats", style=ButtonStyle.PRIMARY, emoji_key="STATS")

    assert btn_en.text == "📊 Statistics"
    assert btn_fa.text == "📊 آمار"
    assert btn_en.callback_data == "adm_nav:stats"
    assert btn_fa.callback_data == "adm_nav:stats"
    EmojiRegistry.reset()


def test_custom_emoji_message_entities() -> None:
    """Verify MessageEntity formatting for Telegram Premium custom emojis."""
    EmojiRegistry.clear()

    # Direct helper entity test
    entity = create_custom_emoji_entity(offset=0, length=2, custom_emoji_id="112233")
    assert entity.type == "custom_emoji"
    assert entity.custom_emoji_id == "112233"

    # Without custom emoji ID -> empty entities list
    text, entities = format_text_with_custom_emojis("VIP Member Status", "VIP")
    assert text == "💎 VIP Member Status"
    assert len(entities) == 0

    # With custom emoji ID -> contains custom_emoji MessageEntity
    EmojiRegistry.set_custom_emoji("VIP", "999888777")
    text, entities = format_text_with_custom_emojis("VIP Member Status", "VIP")
    assert text == "💎 VIP Member Status"
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntity)
    assert entities[0].type == "custom_emoji"
    assert entities[0].custom_emoji_id == "999888777"

    EmojiRegistry.reset()


def test_emoji_registry_enrich_text() -> None:
    """Verify EmojiRegistry.enrich_text transforms plain unicode emojis into <tg-emoji> HTML tags when custom_emoji_id is set."""
    EmojiRegistry.clear()
    EmojiRegistry.set_custom_emoji("STATS", "5249054346200509700")

    raw_text = "📅 Today Statistics"
    enriched = EmojiRegistry.enrich_text(raw_text)

    assert enriched == '<tg-emoji emoji-id="5249054346200509700">📅</tg-emoji> Today Statistics'

    # Verify fallback when no custom emoji is configured
    EmojiRegistry.clear()
    assert EmojiRegistry.enrich_text(raw_text) == raw_text
    EmojiRegistry.reset()

