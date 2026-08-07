import re
from collections.abc import Collection
from urllib.parse import urlparse

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.orm import Session

from app.locales import (
    ACCOUNT_AGE_MESSAGES,
    ACCOUNT_TO_TXT_MESSAGES,
    BACK_LABELS,
    CANCEL_LABELS,
    CLEAN_CHAT_MESSAGES,
    CLEAN_CHAT_MODE_LABELS,
    CLEAN_CHAT_SELECTION_ACTIONS,
    CLEAR_CONTACTS_MESSAGES,
    DELETE_CONTACT_MESSAGES,
    FRESH_SESSION_MESSAGES,
    HELP_BUTTON_LABELS,
    KILL_SESSIONS_MESSAGES,
    LANGUAGES,
    PAYMENT_FLOW_LABELS,
    PRIVACY_SETTINGS_MESSAGES,
    PROFILE_SETUP_MESSAGES,
    READ_OTP_MESSAGES,
    SESSION_TO_JSON_MESSAGES,
    SESSION_TO_TDATA_MESSAGES,
    SPLIT_MESSAGES,
    TDATA_TO_SESSION_MESSAGES,
    get_locale,
    menu_labels,
)
from app.ui import Button, ButtonStyle, EmojiRegistry


def button(
    text: str,
    action: str = "feature:restricted",
    style: ButtonStyle | str | None = None,
    emoji_key: str | None = None,
    is_vip: bool = False,
) -> InlineKeyboardButton:
    custom_emoji_id = EmojiRegistry.get_custom_emoji_id("VIP") if is_vip else None
    btn_text = f"💎 {text}" if (is_vip and not custom_emoji_id) else text
    return Button.create(
        text=btn_text,
        callback_data=action,
        style=style,
        emoji_key=emoji_key or ("VIP" if is_vip else None),
        custom_emoji_id=custom_emoji_id,
    )


def _main_menu(
    language: str, *, direct_file: bool, vip_features: set[str] | None = None
) -> InlineKeyboardMarkup:
    def file_action(tool_action: str, quick_action: str) -> str:
        return quick_action if direct_file else tool_action

    def is_vip(feature_key: str) -> bool:
        return bool(vip_features and feature_key in vip_features)

    label = iter(menu_labels(language))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    f"━━ {next(label)} ━━",
                    "section:noop",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SEARCH",
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:session_check", "quick:session_check"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SEARCH",
                    is_vip=is_vip("session_check"),
                ),
                button(
                    next(label),
                    file_action("tool:spam_check", "quick:spam_check"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SPAM",
                    is_vip=is_vip("spam_check"),
                ),
            ],
            [
                button(
                    next(label),
                    file_action("tool:read_otp", "quick:read_otp"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="OTP",
                    is_vip=is_vip("read_otp"),
                ),
                button(
                    next(label),
                    file_action("tool:check_contacts", "quick:check_contacts"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="CONTACTS",
                    is_vip=is_vip("check_contacts"),
                ),
            ],
            [
                button(
                    f"━━ {next(label)} ━━",
                    "section:noop",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="CONVERT",
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:session_to_tdata", "quick:session_to_tdata"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="CONVERT",
                    is_vip=is_vip("session_to_tdata"),
                ),
                button(
                    next(label),
                    file_action("tool:tdata_to_session", "quick:tdata_to_session"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="CONVERT",
                    is_vip=is_vip("tdata_to_session"),
                ),
            ],
            [
                button(
                    next(label),
                    file_action("tool:session_to_json", "quick:session_to_json"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="EXPORT",
                    is_vip=is_vip("session_to_json"),
                ),
                button(
                    next(label),
                    file_action("tool:account_to_txt", "quick:account_to_txt"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="EXPORT",
                    is_vip=is_vip("account_to_txt"),
                ),
            ],
            [
                button(
                    f"━━ {next(label)} ━━",
                    "section:noop",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SPLIT",
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:split", "quick:file_split"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SPLIT",
                    is_vip=is_vip("split"),
                ),
                button(
                    next(label),
                    file_action("tool:file_merge", "quick:file_merge"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="MERGE",
                    is_vip=is_vip("file_merge"),
                ),
            ],
            [
                button(
                    f"━━ {next(label)} ━━",
                    "section:noop",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SECURITY",
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:change_2fa", "quick:change_2fa"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SECURITY",
                    is_vip=is_vip("change_2fa"),
                ),
                button(
                    next(label),
                    file_action("tool:disable_2fa", "quick:disable_2fa"),
                    style=ButtonStyle.DANGER,
                    emoji_key="UNLOCK",
                    is_vip=is_vip("disable_2fa"),
                ),
            ],
            [
                button(
                    next(label),
                    file_action("tool:reset_2fa", "quick:reset_2fa"),
                    style=ButtonStyle.DANGER,
                    emoji_key="RESET",
                    is_vip=is_vip("reset_2fa"),
                )
            ],
            [
                button(
                    f"━━ {next(label)} ━━",
                    "section:noop",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="BROADCAST",
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:channel_join", "quick:channel_join"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="FORCE_JOIN",
                    is_vip=is_vip("channel_join"),
                ),
                button(
                    next(label),
                    file_action("tool:leave_channel", "quick:leave_channel"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="BACK",
                    is_vip=is_vip("leave_channel"),
                ),
            ],
            [
                button(
                    f"━━ {next(label)} ━━",
                    "section:noop",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="USERS",
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:clean_chat", "quick:clean_chat"),
                    style=ButtonStyle.DANGER,
                    emoji_key="DELETE",
                    is_vip=is_vip("clean_chat"),
                ),
                button(
                    next(label),
                    file_action("tool:clear_contact", "quick:clear_contact"),
                    style=ButtonStyle.DANGER,
                    emoji_key="DELETE",
                    is_vip=is_vip("clear_contact"),
                ),
            ],
            [
                button(
                    next(label),
                    file_action("tool:delete_contact", "quick:delete_contact"),
                    style=ButtonStyle.DANGER,
                    emoji_key="DELETE",
                    is_vip=is_vip("delete_contact"),
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:profile_setup", "quick:profile_setup"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SETTINGS",
                    is_vip=is_vip("profile_setup"),
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:account_age", "quick:account_age"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="STATS",
                    is_vip=is_vip("account_age"),
                )
            ],
            [
                button(
                    f"━━ {next(label)} ━━",
                    "section:noop",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="STATS",
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:mass_message", "quick:mass_message"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="BROADCAST",
                    is_vip=is_vip("mass_message"),
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:kill_sessions", "quick:kill_sessions"),
                    style=ButtonStyle.DANGER,
                    emoji_key="RESET",
                    is_vip=is_vip("kill_sessions"),
                ),
                button(
                    next(label),
                    file_action("tool:fresh_session", "quick:fresh_session"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="REFRESH",
                    is_vip=is_vip("fresh_session"),
                ),
            ],
            [
                button(
                    next(label),
                    file_action("tool:list_checker", "quick:list_checker"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SEARCH",
                    is_vip=is_vip("list_checker"),
                )
            ],
            [
                button(
                    f"━━ {next(label)} ━━",
                    "section:noop",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SECURITY",
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:privacy_settings", "quick:privacy_settings"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SECURITY",
                    is_vip=is_vip("privacy_settings"),
                )
            ],
            [
                button(
                    f"━━ {next(label)} ━━",
                    "section:noop",
                    style=ButtonStyle.SUCCESS,
                    emoji_key="VIP",
                )
            ],
            [
                button(
                    next(label), "menu:plan", style=ButtonStyle.SUCCESS, emoji_key="VIP"
                )
            ],
            [
                button(
                    f"━━ {next(label)} ━━",
                    "section:noop",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SETTINGS",
                )
            ],
            [
                button(
                    next(label),
                    "menu:help",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SUPPORT",
                ),
                button(
                    get_locale(language).language_name.split(maxsplit=1)[-1]
                    if EmojiRegistry.get_custom_emoji_id(f"FLAG_{language.upper()}")
                    else get_locale(language).language_name,
                    "menu:language",
                    style=ButtonStyle.PRIMARY,
                    emoji_key=f"FLAG_{language.upper()}",
                ),
            ],
        ]
    )


def resolve_vip_features(
    vip_features: set[str] | None = None,
    session: Session | None = None,
    session_factory: object | None = None,
) -> set[str]:
    """Query FeatureGateService to determine which features have access_level == VIP_ONLY."""
    if vip_features is not None:
        return vip_features
    if session is not None:
        from app.services.feature_gate import get_vip_feature_keys

        return get_vip_feature_keys(session)
    if session_factory is not None and callable(session_factory):
        from app.services.feature_gate import get_vip_feature_keys

        with session_factory() as db_sess:  # type: ignore[operator]
            return get_vip_feature_keys(db_sess)
    from sqlalchemy.exc import SQLAlchemyError

    from app.db.session import get_default_session_factory

    default_sf = get_default_session_factory()
    if default_sf is not None:
        try:
            from app.services.feature_gate import get_vip_feature_keys

            with default_sf() as db_sess:
                return get_vip_feature_keys(db_sess)
        except SQLAlchemyError:
            return set()
    return set()


def main_menu(
    language: str = "en",
    vip_features: set[str] | None = None,
    session: Session | None = None,
    session_factory: object | None = None,
) -> InlineKeyboardMarkup:
    resolved_vip = resolve_vip_features(vip_features, session, session_factory)
    return _main_menu(language, direct_file=False, vip_features=resolved_vip)


def direct_main_menu(
    language: str = "en",
    vip_features: set[str] | None = None,
    session: Session | None = None,
    session_factory: object | None = None,
) -> InlineKeyboardMarkup:
    resolved_vip = resolve_vip_features(vip_features, session, session_factory)
    return _main_menu(language, direct_file=True, vip_features=resolved_vip)


def resolve_support_contact(support_id: str) -> tuple[str, str] | None:
    value = support_id.strip()
    if not value:
        return None

    if value.isdigit():
        return f"ID: {value}", f"tg://user?id={value}"

    if value.startswith("tg://user?id="):
        numeric_id = value.removeprefix("tg://user?id=")
        if numeric_id.isdigit():
            return f"ID: {numeric_id}", value
        return None

    if value.startswith(("https://t.me/", "http://t.me/", "https://telegram.me/")):
        parsed = urlparse(value)
        value = parsed.path.strip("/").split("/", 1)[0]

    username = value.removeprefix("@").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        return None
    return f"@{username}", f"https://t.me/{username}"


def help_support_menu(support_id: str, language: str = "en") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    contact = resolve_support_contact(support_id)
    if contact is not None:
        display, url = contact
        label = HELP_BUTTON_LABELS.get(language, HELP_BUTTON_LABELS["en"])
        rows.append(
            [
                Button.create(
                    text=f"{label} {display}",
                    url=url,
                    style=ButtonStyle.PRIMARY,
                    emoji_key="MESSAGE",
                )
            ]
        )
    back = BACK_LABELS.get(language, BACK_LABELS["en"])
    rows.append(
        [button(back, "menu:back", style=ButtonStyle.PRIMARY, emoji_key="BACK")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_menu(language: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Button.create(
                    text=CANCEL_LABELS.get(language, CANCEL_LABELS["en"]),
                    callback_data="action:cancel",
                    style=ButtonStyle.DANGER,
                    emoji_key="CANCEL",
                )
            ]
        ]
    )


def file_split_choice_menu(language: str = "en") -> InlineKeyboardMarkup:
    messages = SPLIT_MESSAGES.get(language, SPLIT_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    text=messages["btn_country"],
                    action="split_type:country",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SPLIT_COUNTRY",
                )
            ],
            [
                button(
                    text=messages["btn_quantity"],
                    action="split_type:quantity",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SPLIT_QUANTITY",
                )
            ],
            [
                button(
                    text=messages["btn_cancel"],
                    action="action:cancel",
                    style=ButtonStyle.DANGER,
                    emoji_key="CANCEL",
                )
            ],
        ]
    )


def quick_action_menu(
    language: str = "en",
    vip_features: set[str] | None = None,
    session: Session | None = None,
    session_factory: object | None = None,
) -> InlineKeyboardMarkup:
    resolved_vip = resolve_vip_features(vip_features, session, session_factory)
    return _main_menu(language, direct_file=True, vip_features=resolved_vip)


def file_split_result_menu(
    total: int, split: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    messages = SPLIT_MESSAGES.get(language, SPLIT_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(messages["btn_total"], "split:result:noop", emoji_key="TOTAL"),
                button(str(total), "split:result:noop"),
            ],
            [
                button(messages["btn_split"], "split:result:noop", emoji_key="SPLIT"),
                button(str(split), "split:result:noop"),
            ],
            [
                button(messages["btn_failed"], "split:result:noop", emoji_key="FAILED"),
                button(str(failed), "split:result:noop"),
            ],
        ]
    )


def file_merge_choice_menu(language: str = "en") -> InlineKeyboardMarkup:
    from app.locales import FILE_MERGE_MESSAGES

    msgs = FILE_MERGE_MESSAGES.get(language, FILE_MERGE_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    text=msgs["btn_multi_type"],
                    action="merge_type:multi_type",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="MERGE_MULTI_TYPE",
                )
            ],
            [
                button(
                    text=msgs["btn_session_json_tdata"],
                    action="merge_type:session_json_tdata",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="MERGE_JSON_TDATA",
                )
            ],
            [
                button(
                    text=msgs["btn_cancel"],
                    action="action:cancel",
                    style=ButtonStyle.DANGER,
                    emoji_key="CANCEL",
                )
            ],
        ]
    )


def file_merge_result_menu(
    total: int, merged: int, error: int, language: str = "en"
) -> InlineKeyboardMarkup:
    from app.locales import FILE_MERGE_MESSAGES

    msgs = FILE_MERGE_MESSAGES.get(language, FILE_MERGE_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "file_merge:noop", emoji_key="TOTAL"),
                button(f"{total}", "file_merge:noop"),
            ],
            [
                button(msgs["btn_merged"], "file_merge:noop", emoji_key="CONVERTED"),
                button(f"{merged}", "file_merge:noop"),
            ],
            [
                button(msgs["btn_error"], "file_merge:noop", emoji_key="FAILED"),
                button(f"{error}", "file_merge:noop"),
            ],
        ]
    )


def two_factor_result_menu(
    total: int,
    success: int,
    failed: int,
    language: str = "en",
    *,
    pending: int = 0,
) -> InlineKeyboardMarkup:
    from app.locales import TWO_FACTOR_MESSAGES

    msgs = TWO_FACTOR_MESSAGES.get(language, TWO_FACTOR_MESSAGES["en"])
    rows = [
        [
            button(msgs["btn_total"], "two_factor:noop", emoji_key="TOTAL"),
            button(str(total), "two_factor:noop"),
        ],
        [
            button(msgs["btn_success"], "two_factor:noop", emoji_key="CONVERTED"),
            button(str(success), "two_factor:noop"),
        ],
        [
            button(msgs["btn_failed"], "two_factor:noop", emoji_key="FAILED"),
            button(str(failed), "two_factor:noop"),
        ],
    ]
    if pending:
        rows.insert(
            2,
            [
                button(msgs["btn_pending"], "two_factor:noop", emoji_key="LOADING"),
                button(str(pending), "two_factor:noop"),
            ],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def two_factor_cancel_menu(
    language: str = "en", tool: str = "change"
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    text=CANCEL_LABELS.get(language, CANCEL_LABELS["en"]),
                    action=f"two_factor:cancel:{tool}",
                    style=ButtonStyle.DANGER,
                    emoji_key="CANCEL",
                )
            ]
        ]
    )


def channel_result_menu(
    total: int, success: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    from app.locales import BACK_LABELS, CHANNEL_MESSAGES

    msgs = CHANNEL_MESSAGES.get(language, CHANNEL_MESSAGES["en"])
    back = BACK_LABELS.get(language, BACK_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs['btn_total'], "channel:noop", emoji_key="TOTAL"),
                button(str(total), "channel:noop"),
            ],
            [
                button(msgs['btn_success'], "channel:noop", emoji_key="CONVERTED"),
                button(str(success), "channel:noop"),
            ],
            [
                button(msgs['btn_failed'], "channel:noop", emoji_key="FAILED"),
                button(str(failed), "channel:noop"),
            ],
            [
                button(back, "menu:back", style=ButtonStyle.PRIMARY, emoji_key="BACK"),
            ],
        ]
    )


def language_menu(selected_language: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    for code, locale in LANGUAGES.items():
        emoji_key = f"FLAG_{code.upper()}"
        _, custom_id = EmojiRegistry.resolve_icon(emoji_key)
        if custom_id:
            parts = locale.language_name.split(maxsplit=1)
            text = parts[1] if len(parts) > 1 else locale.language_name
        else:
            text = locale.language_name

        btn = Button.create(
            text=text,
            callback_data=f"language:{code}",
            style=ButtonStyle.PRIMARY,
            emoji_key=emoji_key,
        )
        rows.append([btn])

    start_cb = (
        f"language:start:{selected_language}"
        if selected_language in LANGUAGES
        else "language:start"
    )
    rows.append(
        [
            Button.create(
                text="🚀 /start",
                callback_data=start_cb,
                style=ButtonStyle.SUCCESS,
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def membership_menu(
    channels: tuple[str, ...],
    language: str = "en",
    invite_links: dict[str, str] | None = None,
) -> InlineKeyboardMarkup:
    """Join/Verify keyboard. Public channels link to t.me; private channels
    (no username) fall back to their stored invite link when available."""
    locale = get_locale(language)
    links = invite_links or {}
    rows = []
    for index, channel in enumerate(channels, start=1):
        url = (
            f"https://t.me/{channel[1:]}"
            if channel.startswith("@")
            else links.get(channel)
        )
        if url:
            rows.append(
                [
                    Button.create(
                        text=(
                            locale.join_channel
                            if len(channels) == 1
                            else f"{locale.join_channel} {index}"
                        ),
                        url=url,
                        style=ButtonStyle.PRIMARY,
                        emoji_key="FORCE_JOIN",
                    ),
                    Button.create(
                        text=locale.joined,
                        callback_data=f"membership:check:{language}",
                        style=ButtonStyle.SUCCESS,
                        emoji_key="SUCCESS",
                    ),
                ]
            )
    if not rows:
        rows.append(
            [
                Button.create(
                    text=locale.joined,
                    callback_data=f"membership:check:{language}",
                    style=ButtonStyle.SUCCESS,
                    emoji_key="SUCCESS",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _icon_button(
    label: str,
    action: str,
    emoji_key: str,
    style: ButtonStyle | str | None = None,
) -> InlineKeyboardButton:
    """OTP view button with a premium custom-emoji icon when configured.

    When the registry has a custom_emoji_id for *emoji_key*, the leading
    unicode emoji is stripped from the label and the premium icon is attached
    instead; otherwise the label (with its unicode emoji) is kept unchanged.
    """
    custom_id = EmojiRegistry.get_custom_emoji_id(emoji_key)
    if custom_id:
        head, sep, rest = label.partition(" ")
        if sep and not head.isalnum():
            label = rest
        return InlineKeyboardButton(
            text=label,
            callback_data=action,
            icon_custom_emoji_id=custom_id,
            **({"style": style.value if isinstance(style, ButtonStyle) else style} if style else {}),
        )
    return Button.create(
        text=label, callback_data=action, emoji_key=emoji_key, style=style
    )


def otp_initial_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = READ_OTP_MESSAGES.get(language, READ_OTP_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_icon_button(msgs["btn_check"], "otp:check", "CHECK", style=ButtonStyle.PRIMARY)],
            [_icon_button(msgs["btn_skip"], "otp:skip", "SKIP", style=ButtonStyle.PRIMARY)],
            [
                Button.create(
                    text=cancel_label,
                    callback_data="action:cancel",
                    emoji_key="CANCEL",
                    style=ButtonStyle.DANGER,
                    include_emoji=False,
                )
            ],
        ]
    )


def otp_checked_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = READ_OTP_MESSAGES.get(language, READ_OTP_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_icon_button(msgs["btn_check_again"], "otp:check_again", "REFRESH", style=ButtonStyle.PRIMARY)],
            [_icon_button(msgs["btn_skip"], "otp:skip", "SKIP", style=ButtonStyle.PRIMARY)],
            [
                Button.create(
                    text=cancel_label,
                    callback_data="action:cancel",
                    emoji_key="CANCEL",
                    style=ButtonStyle.DANGER,
                    include_emoji=False,
                )
            ],
        ]
    )


def account_txt_result_menu(
    total: int, converted: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = ACCOUNT_TO_TXT_MESSAGES.get(language, ACCOUNT_TO_TXT_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "account_txt:noop", emoji_key="TOTAL"),
                button(str(total), "account_txt:noop"),
            ],
            [
                button(msgs["btn_converted"], "account_txt:noop", emoji_key="CONVERTED"),
                button(str(converted), "account_txt:noop"),
            ],
            [
                button(msgs["btn_failed"], "account_txt:noop", emoji_key="FAILED"),
                button(str(failed), "account_txt:noop"),
            ],
            [
                button(msgs["btn_retry"], "account_txt:retry", style=ButtonStyle.PRIMARY, emoji_key="REFRESH"),
                button(msgs["btn_home"], "account_txt:home", style=ButtonStyle.PRIMARY, emoji_key="CONTACTS"),
            ],
        ]
    )


def session_json_result_menu(
    total: int, converted: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = SESSION_TO_JSON_MESSAGES.get(language, SESSION_TO_JSON_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "session_json:noop", emoji_key="TOTAL"),
                button(str(total), "session_json:noop"),
            ],
            [
                button(msgs["btn_converted"], "session_json:noop", emoji_key="CONVERTED"),
                button(str(converted), "session_json:noop"),
            ],
            [
                button(msgs["btn_failed"], "session_json:noop", emoji_key="FAILED"),
                button(str(failed), "session_json:noop"),
            ],
            [
                button(msgs["btn_retry"], "session_json:retry", style=ButtonStyle.PRIMARY, emoji_key="REFRESH"),
                button(msgs["btn_home"], "session_json:home", style=ButtonStyle.PRIMARY, emoji_key="CONTACTS"),
            ],
        ]
    )


def session_to_tdata_result_menu(
    total: int, converted: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = SESSION_TO_TDATA_MESSAGES.get(language, SESSION_TO_TDATA_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "session_tdata:noop", emoji_key="TOTAL"),
                button(str(total), "session_tdata:noop"),
            ],
            [
                button(msgs["btn_converted"], "session_tdata:noop", emoji_key="CONVERTED"),
                button(str(converted), "session_tdata:noop"),
            ],
            [
                button(msgs["btn_failed"], "session_tdata:noop", emoji_key="FAILED"),
                button(str(failed), "session_tdata:noop"),
            ],
            [
                button(msgs["btn_retry"], "session_tdata:retry", style=ButtonStyle.PRIMARY, emoji_key="REFRESH"),
                button(msgs["btn_home"], "session_tdata:home", style=ButtonStyle.PRIMARY, emoji_key="CONTACTS"),
            ],
        ]
    )


def tdata_to_session_result_menu(
    total: int, converted: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = TDATA_TO_SESSION_MESSAGES.get(language, TDATA_TO_SESSION_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "tdata_session:noop", emoji_key="TOTAL"),
                button(str(total), "tdata_session:noop"),
            ],
            [
                button(msgs["btn_converted"], "tdata_session:noop", emoji_key="CONVERTED"),
                button(str(converted), "tdata_session:noop"),
            ],
            [
                button(msgs["btn_failed"], "tdata_session:noop", emoji_key="FAILED"),
                button(str(failed), "tdata_session:noop"),
            ],
            [
                button(msgs["btn_retry"], "tdata_session:retry", style=ButtonStyle.PRIMARY, emoji_key="REFRESH"),
                button(msgs["btn_home"], "tdata_session:home", style=ButtonStyle.PRIMARY, emoji_key="CONTACTS"),
            ],
        ]
    )


def clear_contacts_result_menu(
    total: int, cleared: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = CLEAR_CONTACTS_MESSAGES.get(language, CLEAR_CONTACTS_MESSAGES["en"])
    back = BACK_LABELS.get(language, BACK_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "clear_contact:noop", emoji_key="TOTAL"),
                button(str(total), "clear_contact:noop"),
            ],
            [
                button(msgs["btn_success"], "clear_contact:noop", emoji_key="CONVERTED"),
                button(str(cleared), "clear_contact:noop"),
            ],
            [
                button(msgs["btn_failed"], "clear_contact:noop", emoji_key="FAILED"),
                button(str(failed), "clear_contact:noop"),
            ],
            [
                button(back, "menu:back", style=ButtonStyle.PRIMARY, emoji_key="BACK"),
            ],
        ]
    )


def kill_sessions_confirm_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = KILL_SESSIONS_MESSAGES.get(language, KILL_SESSIONS_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _premium_icon_button(
                    msgs["confirm_btn"],
                    "kill_sess:confirm",
                    "KILL",
                    style=ButtonStyle.DANGER,
                )
            ],
            [
                _premium_icon_button(
                    cancel_label, "action:cancel", "CANCEL", style=ButtonStyle.DANGER
                ),
            ],
        ]
    )


def kill_sessions_result_menu(
    total: int, killed: int, fresh: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = KILL_SESSIONS_MESSAGES.get(language, KILL_SESSIONS_MESSAGES["en"])
    back_label = BACK_LABELS.get(language, BACK_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "kill_sess:noop", emoji_key="TOTAL"),
                button(str(total), "kill_sess:noop"),
            ],
            [
                button(msgs["btn_killed"], "kill_sess:noop", emoji_key="CONVERTED"),
                button(str(killed), "kill_sess:noop"),
            ],
            [
                button(msgs["btn_fresh"], "kill_sess:noop", emoji_key="SKIP"),
                button(str(fresh), "kill_sess:noop"),
            ],
            [
                button(msgs["btn_failed"], "kill_sess:noop", emoji_key="FAILED"),
                button(str(failed), "kill_sess:noop"),
            ],
            [
                button(
                    back_label, "menu:back", style=ButtonStyle.PRIMARY, emoji_key="BACK"
                ),
            ],
        ]
    )


def fresh_session_2fa_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = FRESH_SESSION_MESSAGES.get(language, FRESH_SESSION_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _premium_icon_button(
                    msgs["skip_2fa"], "fresh_sess:skip_2fa", "SKIP",
                    style=ButtonStyle.PRIMARY,
                )
            ],
            [
                _premium_icon_button(
                    cancel_label, "action:cancel", "CANCEL", style=ButtonStyle.DANGER
                ),
            ],
        ]
    )


def fresh_session_confirm_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = FRESH_SESSION_MESSAGES.get(language, FRESH_SESSION_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _premium_icon_button(
                    msgs["confirm_btn"],
                    "fresh_sess:confirm",
                    "CONVERT",
                    style=ButtonStyle.SUCCESS,
                )
            ],
            [
                _premium_icon_button(
                    cancel_label, "action:cancel", "CANCEL", style=ButtonStyle.DANGER
                ),
            ],
        ]
    )


def fresh_session_result_menu(
    total: int, succeeded: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = FRESH_SESSION_MESSAGES.get(language, FRESH_SESSION_MESSAGES["en"])
    back_label = BACK_LABELS.get(language, BACK_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "fresh_sess:noop", emoji_key="TOTAL"),
                button(str(total), "fresh_sess:noop"),
            ],
            [
                button(msgs["btn_ok"], "fresh_sess:noop", emoji_key="CONVERTED"),
                button(str(succeeded), "fresh_sess:noop"),
            ],
            [
                button(msgs["btn_failed"], "fresh_sess:noop", emoji_key="FAILED"),
                button(str(failed), "fresh_sess:noop"),
            ],
            [
                button(
                    back_label, "menu:back", style=ButtonStyle.PRIMARY, emoji_key="BACK"
                ),
            ],
        ]
    )


def _premium_icon_button(
    label: str,
    callback_data: str,
    emoji_key: str,
    style: ButtonStyle | str | None = None,
) -> InlineKeyboardButton:
    """Build a button like other premium sections: when a custom emoji ID is
    registered for emoji_key, the leading unicode emoji is stripped from the
    label and the premium icon is attached instead; otherwise the label (with
    its unicode emoji) is kept unchanged."""
    kwargs: dict[str, str | None] = {
        "text": label,
        "callback_data": callback_data,
    }
    if style:
        kwargs["style"] = style.value if isinstance(style, ButtonStyle) else style
    custom_id = EmojiRegistry.get_custom_emoji_id(emoji_key)
    if custom_id:
        clean_label = label.split(" ", 1)[1] if " " in label else label
        kwargs["text"] = clean_label
        kwargs["icon_custom_emoji_id"] = custom_id
    return InlineKeyboardButton(**kwargs)  # type: ignore[arg-type]


def clean_chat_choice_menu(
    language: str = "en", selected: Collection[str] = ()
) -> InlineKeyboardMarkup:
    labels = CLEAN_CHAT_MODE_LABELS.get(language, CLEAN_CHAT_MODE_LABELS["en"])
    actions = CLEAN_CHAT_SELECTION_ACTIONS.get(
        language, CLEAN_CHAT_SELECTION_ACTIONS["en"]
    )
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    selected_set = set(selected)
    categories = ("dms", "bots", "groups", "channels")
    category_emoji_keys = {
        "dms": "DM",
        "bots": "BOT",
        "groups": "GROUP",
        "channels": "CHANNEL",
    }

    def category_button(index: int) -> InlineKeyboardButton:
        category = categories[index]
        marker = "☑️" if category in selected_set else "▫️"
        custom_id = EmojiRegistry.get_custom_emoji_id(category_emoji_keys[category])
        if custom_id:
            label = labels[index]
            clean_label = label.split(" ", 1)[1] if " " in label else label
            return InlineKeyboardButton(
                text=f"{marker} {clean_label}",
                callback_data=f"clean_chat_toggle:{category}",
                icon_custom_emoji_id=custom_id,
                style=ButtonStyle.PRIMARY.value,
            )
        return button(
            f"{marker} {labels[index]}",
            f"clean_chat_toggle:{category}",
            style=ButtonStyle.PRIMARY,
        )

    all_selected = selected_set == set(categories)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [category_button(0), category_button(1)],
            [category_button(2), category_button(3)],
            [
                button(
                    actions["clear_all"] if all_selected else actions["select_all"],
                    "clean_chat_toggle:all",
                    style=ButtonStyle.PRIMARY,
                )
            ],
            [
                _premium_icon_button(
                    actions["confirm"],
                    "clean_chat_confirm",
                    "CONFIRM",
                    style=ButtonStyle.DANGER,
                )
            ],
            [
                button(
                    cancel_label,
                    "action:cancel",
                    style=ButtonStyle.DANGER,
                    emoji_key="CANCEL",
                )
            ],
        ]
    )


def clean_chat_result_menu(
    total: int, cleaned: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = CLEAN_CHAT_MESSAGES.get(language, CLEAN_CHAT_MESSAGES["en"])
    back = BACK_LABELS.get(language, BACK_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "clean_chat:noop", emoji_key="TOTAL"),
                button(str(total), "clean_chat:noop"),
            ],
            [
                button(msgs["btn_success"], "clean_chat:noop", emoji_key="CONVERTED"),
                button(str(cleaned), "clean_chat:noop"),
            ],
            [
                button(msgs["btn_failed"], "clean_chat:noop", emoji_key="FAILED"),
                button(str(failed), "clean_chat:noop"),
            ],
            [
                button(back, "menu:back", style=ButtonStyle.PRIMARY, emoji_key="BACK"),
            ],
        ]
    )


def delete_contact_selection_menu(
    contacts: list[dict],
    selected_ids: set[int],
    page: int = 0,
    page_size: int = 5,
    language: str = "en",
) -> InlineKeyboardMarkup:
    msgs = DELETE_CONTACT_MESSAGES.get(language, DELETE_CONTACT_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    total_contacts = len(contacts)
    total_pages = max(1, (total_contacts + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))

    start_idx = page * page_size
    end_idx = min(start_idx + page_size, total_contacts)
    page_contacts = contacts[start_idx:end_idx]

    rows: list[list[InlineKeyboardButton]] = []
    for c in page_contacts:
        uid = c["user_id"]
        is_selected = uid in selected_ids
        prefix = (
            EmojiRegistry.format_text_emoji("CHECKBOX")
            if is_selected
            else "◻️"
        )
        first = c.get("first_name") or ""
        last = c.get("last_name") or ""
        phone = c.get("phone") or ""
        name_str = f"{first} {last}".strip() or str(uid)
        display_str = f"{prefix} {name_str}"
        if phone:
            display_str += f" ({phone})"
        if len(display_str) > 35:
            display_str = display_str[:32] + "..."
        rows.append(
            [
                InlineKeyboardButton(
                    text=display_str,
                    callback_data=f"del_cnt_toggle:{uid}",
                    style=ButtonStyle.PRIMARY.value,
                )
            ]
        )

    # Navigation row
    prev_btn = InlineKeyboardButton(
        text=EmojiRegistry.format_text_emoji("BACK") if page > 0 else " ",
        callback_data=f"del_cnt_page:{page - 1}" if page > 0 else "del_cnt:noop",
        style=ButtonStyle.PRIMARY.value,
    )
    page_indicator = InlineKeyboardButton(
        text=f"📄 {page + 1}/{total_pages}", callback_data="del_cnt:noop"
    )
    next_btn = InlineKeyboardButton(
        text=EmojiRegistry.format_text_emoji("NEXT")
        if page < total_pages - 1
        else " ",
        callback_data=f"del_cnt_page:{page + 1}"
        if page < total_pages - 1
        else "del_cnt:noop",
        style=ButtonStyle.PRIMARY.value,
    )
    rows.append([prev_btn, page_indicator, next_btn])

    # Action row (Select All / Deselect All)
    rows.append(
        [
            InlineKeyboardButton(
                text=msgs["select_all"],
                callback_data="del_cnt_action:select_all",
                style=ButtonStyle.PRIMARY.value,
            ),
            InlineKeyboardButton(
                text=msgs["deselect_all"],
                callback_data="del_cnt_action:deselect_all",
                style=ButtonStyle.PRIMARY.value,
            ),
        ]
    )

    # Delete Selected button row
    selected_count = len(selected_ids)
    del_text = msgs["delete_btn"].format(count=selected_count)
    rows.append(
        [
            InlineKeyboardButton(
                text=del_text,
                callback_data="del_cnt_action:confirm"
                if selected_count > 0
                else "del_cnt_action:noop_empty",
                style=ButtonStyle.DANGER.value,
            )
        ]
    )

    # Cancel row
    rows.append(
        [button(cancel_label, "action:cancel", style=ButtonStyle.DANGER)]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_contact_result_menu(
    total: int, deleted: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = DELETE_CONTACT_MESSAGES.get(language, DELETE_CONTACT_MESSAGES["en"])
    back = BACK_LABELS.get(language, BACK_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "del_cnt:noop", emoji_key="TOTAL"),
                button(str(total), "del_cnt:noop"),
            ],
            [
                button(msgs["btn_deleted"], "del_cnt:noop", emoji_key="DELETE"),
                button(str(deleted), "del_cnt:noop"),
            ],
            [
                button(msgs["btn_failed"], "del_cnt:noop", emoji_key="FAILED"),
                button(str(failed), "del_cnt:noop"),
            ],
            [
                button(back, "menu:back", style=ButtonStyle.PRIMARY, emoji_key="BACK"),
            ],
        ]
    )


def profile_setup_account_menu(
    language: str = "en",
) -> InlineKeyboardMarkup:
    msgs = PROFILE_SETUP_MESSAGES.get(language, PROFILE_SETUP_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    msgs["btn_edit_name"],
                    "prof_setup:edit_name",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="EDIT",
                ),
                button(
                    msgs["btn_edit_username"],
                    "prof_setup:edit_username",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="USERNAME",
                ),
            ],
            [
                button(
                    msgs["btn_edit_about"],
                    "prof_setup:edit_about",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="MESSAGE",
                ),
                button(
                    msgs["btn_set_photo"],
                    "prof_setup:set_photo",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="PHOTO",
                ),
            ],
            [
                button(
                    msgs["btn_apply"],
                    "prof_setup:apply",
                    style=ButtonStyle.SUCCESS,
                    emoji_key="SUCCESS",
                ),
            ],
            [
                button(
                    msgs["btn_skip"],
                    "prof_setup:skip",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SKIP",
                ),
            ],
            [
                button(
                    cancel_label,
                    "flow:cancel",
                    style=ButtonStyle.DANGER,
                    emoji_key="CANCEL",
                ),
            ],
        ]
    )


def profile_setup_result_menu(
    total: int, modified: int, skipped: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = PROFILE_SETUP_MESSAGES.get(language, PROFILE_SETUP_MESSAGES["en"])
    back = BACK_LABELS.get(language, BACK_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "prof_setup:noop", emoji_key="TOTAL"),
                button(str(total), "prof_setup:noop"),
            ],
            [
                button(msgs["btn_modified"], "prof_setup:noop", emoji_key="CONVERTED"),
                button(str(modified), "prof_setup:noop"),
            ],
            [
                button(msgs["btn_skipped"], "prof_setup:noop", emoji_key="SKIP"),
                button(str(skipped), "prof_setup:noop"),
            ],
            [
                button(msgs["btn_failed"], "prof_setup:noop", emoji_key="FAILED"),
                button(str(failed), "prof_setup:noop"),
            ],
            [
                button(back, "menu:back", style=ButtonStyle.PRIMARY, emoji_key="BACK"),
            ],
        ]
    )


def account_age_result_menu(
    total: int,
    checked: int,
    failed: int,
    language: str = "en",
    *,
    page: int = 0,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    msgs = ACCOUNT_AGE_MESSAGES.get(language, ACCOUNT_AGE_MESSAGES["en"])
    back = BACK_LABELS.get(language, BACK_LABELS["en"])
    rows: list[list[InlineKeyboardButton]] = []

    if total_pages > 1:
        nav_row: list[InlineKeyboardButton] = []
        nav_row.append(
            InlineKeyboardButton(
                text="⏮" if page > 0 else " ",
                callback_data="acc_age_page:0" if page > 0 else "acc_age:noop",
                style=ButtonStyle.PRIMARY.value,
            )
        )

        nav_row.append(
            InlineKeyboardButton(
                text=msgs["btn_prev"] if page > 0 else " ",
                callback_data=f"acc_age_page:{page - 1}"
                if page > 0
                else "acc_age:noop",
                style=ButtonStyle.PRIMARY.value,
            )
        )

        nav_row.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="acc_age:noop",
            )
        )

        nav_row.append(
            InlineKeyboardButton(
                text=msgs["btn_next"] if page < total_pages - 1 else " ",
                callback_data=f"acc_age_page:{page + 1}"
                if page < total_pages - 1
                else "acc_age:noop",
                style=ButtonStyle.PRIMARY.value,
            )
        )

        if total_pages > 5:
            nav_row.append(
                InlineKeyboardButton(
                    text="⏭" if page < total_pages - 1 else " ",
                    callback_data=f"acc_age_page:{total_pages - 1}"
                    if page < total_pages - 1
                    else "acc_age:noop",
                    style=ButtonStyle.PRIMARY.value,
                )
            )

        rows.append(nav_row)

    rows.append(
        [
            button(msgs["btn_total"], "acc_age:noop", emoji_key="TOTAL"),
            button(str(total), "acc_age:noop"),
        ]
    )
    rows.append(
        [
            button(msgs["btn_checked"], "acc_age:noop", emoji_key="CHECK"),
            button(str(checked), "acc_age:noop"),
        ]
    )
    rows.append(
        [
            button(msgs["btn_failed"], "acc_age:noop", emoji_key="FAILED"),
            button(str(failed), "acc_age:noop"),
        ]
    )
    rows.append(
        [
            button(back, "menu:back", style=ButtonStyle.PRIMARY, emoji_key="BACK"),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def mass_message_recipients_menu(language: str = "en") -> InlineKeyboardMarkup:
    from app.locales import MASS_MESSAGE_MESSAGES

    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _premium_icon_button(
                    msgs["btn_use_contacts"],
                    "mass_msg_recipients:contacts",
                    "CARD",
                    style=ButtonStyle.PRIMARY,
                )
            ],
            [
                _premium_icon_button(
                    cancel_label, "action:cancel", "CANCEL", style=ButtonStyle.DANGER
                )
            ],
        ]
    )


def mass_message_delay_menu(language: str = "en") -> InlineKeyboardMarkup:
    from app.locales import MASS_MESSAGE_MESSAGES

    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _premium_icon_button(
                    msgs["btn_delay_fast"], "mass_msg_delay:10_20", "FAST",
                    style=ButtonStyle.PRIMARY,
                )
            ],
            [
                _premium_icon_button(
                    msgs["btn_delay_balanced"], "mass_msg_delay:20_60", "BALANCED",
                    style=ButtonStyle.PRIMARY,
                )
            ],
            [
                _premium_icon_button(
                    msgs["btn_delay_safe"], "mass_msg_delay:60_120", "SPAM",
                    style=ButtonStyle.PRIMARY,
                )
            ],
            [
                _premium_icon_button(
                    cancel_label, "action:cancel", "CANCEL", style=ButtonStyle.DANGER
                )
            ],
        ]
    )


def mass_message_confirm_menu(language: str = "en") -> InlineKeyboardMarkup:
    from app.locales import MASS_MESSAGE_MESSAGES

    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _premium_icon_button(
                    msgs["btn_start"],
                    "mass_msg_action:start",
                    "CONFIRM",
                    style=ButtonStyle.SUCCESS,
                )
            ],
            [
                _premium_icon_button(
                    cancel_label, "action:cancel", "CANCEL", style=ButtonStyle.DANGER
                )
            ],
        ]
    )


def mass_message_live_menu(
    is_paused: bool = False, language: str = "en"
) -> InlineKeyboardMarkup:
    from app.locales import MASS_MESSAGE_MESSAGES

    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
    pause_resume_btn = (
        _premium_icon_button(
            msgs["btn_resume"],
            "mass_msg_ctrl:resume",
            "NEXT_PAGE",
            style=ButtonStyle.SUCCESS,
        )
        if is_paused
        else _premium_icon_button(
            msgs["btn_pause"],
            "mass_msg_ctrl:pause",
            "PAUSE",
            style=ButtonStyle.PRIMARY,
        )
    )
    stop_btn = _premium_icon_button(
        msgs["btn_stop"], "mass_msg_ctrl:stop", "STOP", style=ButtonStyle.DANGER
    )
    return InlineKeyboardMarkup(inline_keyboard=[[pause_resume_btn, stop_btn]])


def mass_message_paused_menu(job_id: str, language: str = "en") -> InlineKeyboardMarkup:
    from app.locales import MASS_MESSAGE_MESSAGES

    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _premium_icon_button(
                    msgs["btn_resume"],
                    f"resume_job:{job_id}",
                    "NEXT_PAGE",
                    style=ButtonStyle.SUCCESS,
                )
            ],
            [
                _premium_icon_button(
                    cancel_label, "menu:back", "CANCEL", style=ButtonStyle.DANGER
                ),
            ],
        ]
    )


def list_checker_cancel_menu(language: str = "en") -> InlineKeyboardMarkup:
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    cancel_label,
                    "action:cancel",
                    style=ButtonStyle.DANGER,
                    emoji_key="CANCEL",
                )
            ]
        ]
    )


def list_checker_result_menu(
    tdata: int, session: int, json_cnt: int, total: int, language: str = "en"
) -> InlineKeyboardMarkup:
    back_label = BACK_LABELS.get(language, BACK_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button("Tdata", "list_check:noop", emoji_key="CONTACTS"),
                button(str(tdata), "list_check:noop"),
            ],
            [
                button("Session", "list_check:noop", emoji_key="SESSION"),
                button(str(session), "list_check:noop"),
            ],
            [
                button("JSON", "list_check:noop", emoji_key="EXPORT"),
                button(str(json_cnt), "list_check:noop"),
            ],
            [
                button("Total", "list_check:noop", emoji_key="TOTAL"),
                button(str(total), "list_check:noop"),
            ],
            [
                button(
                    back_label, "menu:back", style=ButtonStyle.PRIMARY, emoji_key="BACK"
                ),
            ],
        ]
    )


# Semantic emoji key per privacy rule (resolves to env premium IDs when configured)
PRIVACY_RULE_EMOJI_KEYS: dict[str, str] = {
    "last_seen": "VIEW",
    "phone_number": "PHONE",
    "profile_photo": "PHOTO",
    "forwarded_messages": "MESSAGE",
    "calls": "CALLS",
    "p2p_calls": "LINK",
    "group_invites": "GROUP",
    "voice_messages": "VOICE",
}


def privacy_2fa_menu(language: str = "en") -> InlineKeyboardMarkup:
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    "Skip",
                    "privacy:skip_2fa",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SKIP",
                )
            ],
            [
                button(
                    cancel_label,
                    "action:cancel",
                    style=ButtonStyle.DANGER,
                    emoji_key="CANCEL",
                )
            ],
        ]
    )


def privacy_mode_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    msgs["btn_preset"],
                    "privacy:mode:preset",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="STATS",
                )
            ],
            [
                button(
                    msgs["btn_custom"],
                    "privacy:mode:custom",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SETTINGS",
                )
            ],
            [
                button(
                    cancel_label,
                    "action:cancel",
                    style=ButtonStyle.DANGER,
                    emoji_key="CANCEL",
                )
            ],
        ]
    )


def privacy_presets_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    presets = msgs["presets"]
    back_label = BACK_LABELS.get(language, BACK_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    presets["maximum"],
                    "privacy:preset:maximum",
                    style=ButtonStyle.DANGER,
                    emoji_key="DANGER",
                )
            ],
            [
                button(
                    presets["medium"],
                    "privacy:preset:medium",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="FROZEN",
                )
            ],
            [
                button(
                    presets["open"],
                    "privacy:preset:open",
                    style=ButtonStyle.SUCCESS,
                    emoji_key="ACTIVE",
                )
            ],
            [
                button(
                    back_label,
                    "privacy:back_mode",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="BACK",
                )
            ],
        ]
    )


def privacy_custom_menu(
    language: str = "en", current_rules: dict[str, str] | None = None
) -> InlineKeyboardMarkup:
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    rules_dict = msgs["rules"]
    values_dict = msgs["values"]
    rules_state = current_rules or {}
    back_label = BACK_LABELS.get(language, BACK_LABELS["en"])

    rows = []
    for key, name in rules_dict.items():
        val = rules_state.get(key, "nobody")
        val_name = values_dict.get(val, val)
        rows.append(
            [
                button(
                    f"{name}: {val_name}",
                    f"privacy:rule:{key}",
                    style=ButtonStyle.PRIMARY,
                    emoji_key=PRIVACY_RULE_EMOJI_KEYS.get(key),
                )
            ]
        )

    rows.append(
        [
            button(
                msgs["btn_apply_custom"],
                "privacy:apply_custom",
                style=ButtonStyle.SUCCESS,
                emoji_key="SUCCESS",
            )
        ]
    )
    rows.append(
        [
            button(
                back_label,
                "privacy:back_mode",
                style=ButtonStyle.PRIMARY,
                emoji_key="BACK",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def privacy_value_menu(
    language: str = "en", rule_key: str = ""
) -> InlineKeyboardMarkup:
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    values_dict = msgs["values"]
    back_label = BACK_LABELS.get(language, BACK_LABELS["en"])

    rows = [
        [
            button(
                values_dict["everybody"],
                f"privacy:val:{rule_key}:everybody",
                style=ButtonStyle.PRIMARY,
                emoji_key="WORLD",
            )
        ],
        [
            button(
                values_dict["contacts"],
                f"privacy:val:{rule_key}:contacts",
                style=ButtonStyle.PRIMARY,
                emoji_key="CONTACTS",
            )
        ],
        [
            button(
                values_dict["nobody"],
                f"privacy:val:{rule_key}:nobody",
                style=ButtonStyle.DANGER,
                emoji_key="BANNED",
            )
        ],
        [
            button(
                back_label,
                "privacy:back_custom",
                style=ButtonStyle.PRIMARY,
                emoji_key="BACK",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def privacy_result_menu(
    total: int, succeeded: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "privacy:noop", emoji_key="TOTAL"),
                button(str(total), "privacy:noop"),
            ],
            [
                button(msgs["btn_ok"], "privacy:noop", emoji_key="CONVERTED"),
                button(str(succeeded), "privacy:noop"),
            ],
            [
                button(msgs["btn_failed"], "privacy:noop", emoji_key="FAILED"),
                button(str(failed), "privacy:noop"),
            ],
        ]
    )


def proxy_menu(has_proxy: bool = False, language: str = "en") -> InlineKeyboardMarkup:
    labels = {
        "en": {
            "set": "⚙️ Set Proxy",
            "view": "📡 View Current Proxy",
            "remove": "🗑️ Remove Proxy",
            "back": "⬅️ Back",
        },
        "bn": {
            "set": "⚙️ প্রক্সি সেট করুন",
            "view": "📡 বর্তমান প্রক্সি দেখুন",
            "remove": "🗑️ প্রক্সি রিমুভ করুন",
            "back": "⬅️ ব্যাক",
        },
        "hi": {
            "set": "⚙️ प्रॉक्सी सेट करें",
            "view": "📡 वर्तमान प्रॉक्सी देखें",
            "remove": "🗑️ प्रॉक्सी हटाएं",
            "back": "⬅️ वापस",
        },
        "ur": {
            "set": "⚙️ پروکسی سیٹ کریں",
            "view": "📡 موجودہ پروکسی دیکھیں",
            "remove": "🗑️ پروکسی ختم کریں",
            "back": "⬅️ واپس",
        },
        "ar": {
            "set": "⚙️ ضبط البروكسي",
            "view": "📡 عرض البروكسي الحالي",
            "remove": "🗑️ إزالة البروكسي",
            "back": "⬅️ عودة",
        },
        "zh": {
            "set": "⚙️ 设置代理",
            "view": "📡 查看当前代理",
            "remove": "🗑️ 删除代理",
            "back": "⬅️ 返回",
        },
    }
    l = labels.get(language, labels["en"])
    rows = [
        [button(l["set"], "proxy:set", style=ButtonStyle.PRIMARY, emoji_key="SETTINGS")],
        [button(l["view"], "proxy:view", style=ButtonStyle.PRIMARY, emoji_key="SEARCH")],
    ]
    if has_proxy:
        rows.append(
            [button(l["remove"], "proxy:remove", style=ButtonStyle.DANGER, emoji_key="DELETE")]
        )
    rows.append(
        [button(l["back"], "menu:back", style=ButtonStyle.PRIMARY, emoji_key="BACK")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_vip_plans_menu(plans: list, language: str = "en") -> InlineKeyboardMarkup:
    """Generate dynamic user VIP purchase plans keyboard."""
    kb = []
    for p in plans:
        kb.append(
            [
                Button.create(
                    text=f"{p.name} — {p.price} USD",
                    callback_data=f"buy_plan:{p.id}",
                    style=ButtonStyle.SUCCESS,
                    emoji_key="VIP",
                )
            ]
        )
    back_lbl = BACK_LABELS.get(language, BACK_LABELS["en"])
    kb.append(
        [
            Button.create(
                text=back_lbl,
                callback_data="menu:back",
                style=ButtonStyle.PRIMARY,
                emoji_key="BACK",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=kb)


def vip_checkout_menu(language: str = "en") -> InlineKeyboardMarkup:
    """Generate inline keyboard for VIP checkout page with Back & Cancel buttons."""
    back_lbl = BACK_LABELS.get(language, BACK_LABELS["en"])
    cancel_lbl = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Button.create(
                    text=back_lbl,
                    callback_data="menu:plan",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="BACK",
                ),
                Button.create(
                    text=cancel_lbl,
                    callback_data="action:cancel",
                    style=ButtonStyle.DANGER,
                    emoji_key="CANCEL",
                ),
            ]
        ]
    )


def vip_payment_method_menu(
    language: str = "en",
    manual_enabled: bool = True,
    auto_enabled: bool = True,
) -> InlineKeyboardMarkup:
    """Generate VIP checkout payment-method choice keyboard (manual + auto)."""
    labels = PAYMENT_FLOW_LABELS.get(language, PAYMENT_FLOW_LABELS["en"])
    back_lbl = BACK_LABELS.get(language, BACK_LABELS["en"])
    cancel_lbl = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    method_buttons = []
    if manual_enabled:
        method_buttons.append(
            _premium_icon_button(
                labels["manual"],
                "pay_method:manual",
                "PAYMENT",
                style=ButtonStyle.SUCCESS,
            )
        )
    if auto_enabled:
        method_buttons.append(
            _premium_icon_button(
                labels["auto"],
                "pay_method:auto",
                "BOT",
                style=ButtonStyle.PRIMARY,
            )
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            method_buttons,
            [
                _premium_icon_button(
                    back_lbl, "menu:plan", "BACK", style=ButtonStyle.PRIMARY
                ),
                _premium_icon_button(
                    cancel_lbl, "action:cancel", "CANCEL", style=ButtonStyle.DANGER
                ),
            ],
        ]
    )


def manual_payment_done_menu(language: str = "en") -> InlineKeyboardMarkup:
    """Generate manual-payment screen keyboard with send-screenshot & cancel."""
    labels = PAYMENT_FLOW_LABELS.get(language, PAYMENT_FLOW_LABELS["en"])
    cancel_lbl = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _premium_icon_button(
                    labels["send_screenshot"],
                    "pay:manual_screenshot",
                    "PHOTO",
                    style=ButtonStyle.SUCCESS,
                )
            ],
            [
                _premium_icon_button(
                    cancel_lbl, "action:cancel", "CANCEL", style=ButtonStyle.DANGER
                )
            ],
        ]
    )


def auto_payment_control_menu(language: str = "en") -> InlineKeyboardMarkup:
    """Generate auto-payment keyboard with check-payment & cancel buttons."""
    labels = PAYMENT_FLOW_LABELS.get(language, PAYMENT_FLOW_LABELS["en"])
    cancel_lbl = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _premium_icon_button(
                    labels["check_payment"],
                    "pay:auto_check",
                    "REFRESH",
                    style=ButtonStyle.PRIMARY,
                )
            ],
            [
                _premium_icon_button(
                    cancel_lbl, "action:cancel", "CANCEL", style=ButtonStyle.DANGER
                )
            ],
        ]
    )
