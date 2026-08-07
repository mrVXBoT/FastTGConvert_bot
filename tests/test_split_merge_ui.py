"""UI tests for File Split / File Merge premium emoji integration."""

from app.keyboards import (
    file_merge_choice_menu,
    file_merge_result_menu,
    file_split_choice_menu,
    file_split_result_menu,
)
from app.locales import LANGUAGES, SPLIT_MESSAGES
from app.ui import EmojiRegistry


def _load() -> None:
    EmojiRegistry.reset()
    EmojiRegistry.set_custom_emoji("SPLIT_COUNTRY", "5211157547645421280")
    EmojiRegistry.set_custom_emoji("SPLIT_QUANTITY", "5210729536974503652")
    EmojiRegistry.set_custom_emoji("TOTAL", "5821421565174092291")
    EmojiRegistry.set_custom_emoji("CONVERTED", "5940635490645449104")
    EmojiRegistry.set_custom_emoji("FAILED", "5940804914220372462")
    EmojiRegistry.set_custom_emoji("MERGE", "5463123191339715467")
    EmojiRegistry.set_custom_emoji("SPLIT", "5278551434265135459")
    EmojiRegistry.set_custom_emoji("MERGE_MULTI_TYPE", "6298486951657867390")
    EmojiRegistry.set_custom_emoji("MERGE_JSON_TDATA", "6296504553667823627")
    EmojiRegistry.set_custom_emoji("REFRESH", "5465144931230190889")
    EmojiRegistry.set_custom_emoji("CONTACTS", "5343909794149310690")
    EmojiRegistry.load_flag_pack()


def test_split_choice_buttons_single_premium_emoji() -> None:
    _load()
    for language in LANGUAGES:
        menu = file_split_choice_menu(language)
        country, quantity = menu.inline_keyboard[0][0], menu.inline_keyboard[1][0]
        assert country.icon_custom_emoji_id == "5211157547645421280"
        assert quantity.icon_custom_emoji_id == "5210729536974503652"
        assert "🗺️" not in country.text and "🔢" not in quantity.text
        assert country.callback_data == "split_type:country"
        assert quantity.callback_data == "split_type:quantity"


def test_split_choice_buttons_fallback_single_emoji() -> None:
    EmojiRegistry.reset()
    menu = file_split_choice_menu("en")
    country = menu.inline_keyboard[0][0]
    assert country.icon_custom_emoji_id is None
    assert country.text == "🗺️ Split by Country"


def test_split_result_menu_uses_total_and_failed() -> None:
    _load()
    menu = file_split_result_menu(3, 2, 1, "en")
    rows = menu.inline_keyboard
    assert rows[0][0].icon_custom_emoji_id == "5821421565174092291"
    assert rows[1][0].icon_custom_emoji_id == "5278551434265135459" or rows[1][0].text == "✂️ Split"
    assert rows[2][0].icon_custom_emoji_id == "5940804914220372462"


def test_merge_choice_buttons_single_premium_emoji() -> None:
    _load()
    for language in LANGUAGES:
        menu = file_merge_choice_menu(language)
        multi, merged = menu.inline_keyboard[0][0], menu.inline_keyboard[1][0]
        assert multi.icon_custom_emoji_id == "6298486951657867390"
        assert merged.icon_custom_emoji_id == "6296504553667823627"
        assert "📦" not in multi.text and "📦" not in merged.text
        assert multi.callback_data == "merge_type:multi_type"
        assert merged.callback_data == "merge_type:session_json_tdata"


def test_merge_result_menu_uses_metrics() -> None:
    _load()
    menu = file_merge_result_menu(3, 2, 1, "en")
    rows = menu.inline_keyboard
    assert rows[0][0].icon_custom_emoji_id == "5821421565174092291"
    assert rows[1][0].icon_custom_emoji_id == "5940635490645449104"
    assert rows[2][0].icon_custom_emoji_id == "5940804914220372462"
    assert rows[0][0].text == "Total"


def test_enrich_upgrades_tool_flow_emojis() -> None:
    _load()
    text = EmojiRegistry.enrich(
        "✂️ <b>Choose file split type</b>\n\n📦 Found <b>3</b> sessions"
    )
    assert '<tg-emoji emoji-id="5211157547645421280">🗺️</tg-emoji>' not in text
    assert 'emoji-id="5278551434265135459">✂️</tg-emoji>' in text
    assert 'emoji-id="5821421565174092291">📦</tg-emoji>' in text


def test_enrich_flags_upgrades_country_flags() -> None:
    _load()
    text = EmojiRegistry.enrich_flags("🇳🇬 Nigeria — 1 sessions")
    assert '<tg-emoji emoji-id="5294130362979465506">🇳🇬</tg-emoji>' in text
    text = EmojiRegistry.enrich_flags("🌍 Unknown — 1 sessions")
    assert "<tg-emoji" not in text


def test_split_caption_locale_has_flag_slot() -> None:
    for language in LANGUAGES:
        assert "{flag}" in SPLIT_MESSAGES[language]["caption_country"]
        assert not SPLIT_MESSAGES[language]["btn_country"].startswith("🗺️")
        assert not SPLIT_MESSAGES[language]["btn_quantity"].startswith("🔢")
