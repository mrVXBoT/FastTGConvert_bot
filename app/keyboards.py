import re
from collections.abc import Collection
from urllib.parse import urlparse

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.locales import (
    ACCOUNT_AGE_MESSAGES,
    ACCOUNT_TO_TXT_MESSAGES,
    BACK_LABELS,
    CANCEL_LABELS,
    CHECK_CONTACTS_MESSAGES,
    CLEAN_CHAT_MESSAGES,
    CLEAN_CHAT_MODE_LABELS,
    CLEAN_CHAT_SELECTION_ACTIONS,
    CLEAR_CONTACTS_MESSAGES,
    DELETE_CONTACT_MESSAGES,
    FRESH_SESSION_MESSAGES,
    HELP_BUTTON_LABELS,
    KILL_SESSIONS_MESSAGES,
    LANGUAGES,
    PRIVACY_SETTINGS_MESSAGES,
    PROFILE_SETUP_MESSAGES,
    READ_OTP_MESSAGES,
    SESSION_TO_JSON_MESSAGES,
    SPLIT_MESSAGES,
    get_locale,
    menu_labels,
)
from app.ui import Button, ButtonStyle, EmojiRegistry


def button(
    text: str,
    action: str = "feature:restricted",
    style: ButtonStyle | str | None = None,
    emoji_key: str | None = None,
) -> InlineKeyboardButton:
    return Button.create(text=text, callback_data=action, style=style, emoji_key=emoji_key)


def _main_menu(language: str, *, direct_file: bool) -> InlineKeyboardMarkup:
    def file_action(tool_action: str, quick_action: str) -> str:
        return quick_action if direct_file else tool_action

    label = iter(menu_labels(language))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [button(f"━━ {next(label)} ━━", "section:noop", style=ButtonStyle.PRIMARY, emoji_key="SEARCH")],
            [
                button(
                    next(label),
                    file_action("tool:session_check", "quick:session_check"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SEARCH",
                ),
                button(
                    next(label),
                    file_action("tool:spam_check", "quick:spam_check"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SPAM",
                ),
            ],
            [
                button(
                    next(label),
                    file_action("tool:read_otp", "quick:read_otp"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="OTP",
                ),
                button(
                    next(label),
                    file_action("tool:check_contacts", "quick:check_contacts"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="CONTACTS",
                ),
            ],
            [button(f"━━ {next(label)} ━━", "section:noop", style=ButtonStyle.PRIMARY, emoji_key="CONVERT")],
            [
                button(
                    next(label),
                    file_action("tool:session_to_tdata", "quick:session_to_tdata"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="CONVERT",
                ),
                button(
                    next(label),
                    file_action("tool:tdata_to_session", "quick:tdata_to_session"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="CONVERT",
                ),
            ],
            [
                button(
                    next(label),
                    file_action("tool:session_to_json", "quick:session_to_json"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="EXPORT",
                ),
                button(
                    next(label),
                    file_action("tool:account_to_txt", "quick:account_to_txt"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="EXPORT",
                ),
            ],
            [button(f"━━ {next(label)} ━━", "section:noop", style=ButtonStyle.PRIMARY, emoji_key="SPLIT")],
            [
                button(
                    next(label),
                    file_action("tool:split", "quick:file_split"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SPLIT",
                ),
                button(
                    next(label),
                    file_action("tool:file_merge", "quick:file_merge"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="MERGE",
                ),
            ],
            [button(f"━━ {next(label)} ━━", "section:noop", style=ButtonStyle.PRIMARY, emoji_key="SECURITY")],
            [
                button(
                    next(label),
                    file_action("tool:change_2fa", "quick:change_2fa"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SECURITY",
                ),
                button(
                    next(label),
                    file_action("tool:disable_2fa", "quick:disable_2fa"),
                    style=ButtonStyle.DANGER,
                    emoji_key="UNLOCK",
                ),
            ],
            [
                button(
                    next(label),
                    file_action("tool:reset_2fa", "quick:reset_2fa"),
                    style=ButtonStyle.DANGER,
                    emoji_key="RESET",
                )
            ],
            [button(f"━━ {next(label)} ━━", "section:noop", style=ButtonStyle.PRIMARY, emoji_key="BROADCAST")],
            [
                button(
                    next(label),
                    file_action("tool:channel_join", "quick:channel_join"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="FORCE_JOIN",
                ),
                button(
                    next(label),
                    file_action("tool:leave_channel", "quick:leave_channel"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="BACK",
                ),
            ],
            [button(f"━━ {next(label)} ━━", "section:noop", style=ButtonStyle.PRIMARY, emoji_key="USERS")],
            [
                button(
                    next(label),
                    file_action("tool:clean_chat", "quick:clean_chat"),
                    style=ButtonStyle.DANGER,
                    emoji_key="DELETE",
                ),
                button(
                    next(label),
                    file_action("tool:clear_contact", "quick:clear_contact"),
                    style=ButtonStyle.DANGER,
                    emoji_key="DELETE",
                ),
            ],
            [
                button(
                    next(label),
                    file_action("tool:delete_contact", "quick:delete_contact"),
                    style=ButtonStyle.DANGER,
                    emoji_key="DELETE",
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:profile_setup", "quick:profile_setup"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SETTINGS",
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:account_age", "quick:account_age"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="STATS",
                )
            ],
            [button(f"━━ {next(label)} ━━", "section:noop", style=ButtonStyle.PRIMARY, emoji_key="STATS")],
            [
                button(
                    next(label),
                    file_action("tool:mass_message", "quick:mass_message"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="BROADCAST",
                )
            ],
            [
                button(
                    next(label),
                    file_action("tool:kill_sessions", "quick:kill_sessions"),
                    style=ButtonStyle.DANGER,
                    emoji_key="RESET",
                ),
                button(
                    next(label),
                    file_action("tool:fresh_session", "quick:fresh_session"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="REFRESH",
                ),
            ],
            [
                button(
                    next(label),
                    file_action("tool:list_checker", "quick:list_checker"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SEARCH",
                )
            ],
            [button(f"━━ {next(label)} ━━", "section:noop", style=ButtonStyle.PRIMARY, emoji_key="SECURITY")],
            [
                button(
                    next(label),
                    file_action("tool:privacy_settings", "quick:privacy_settings"),
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SECURITY",
                )
            ],
            [button(f"━━ {next(label)} ━━", "section:noop", style=ButtonStyle.SUCCESS, emoji_key="VIP")],
            [button(next(label), "menu:plan", style=ButtonStyle.SUCCESS, emoji_key="VIP")],
            [button(f"━━ {next(label)} ━━", "section:noop", style=ButtonStyle.PRIMARY, emoji_key="SETTINGS")],
            [
                button(next(label), "menu:help", style=ButtonStyle.PRIMARY, emoji_key="SUPPORT"),
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


def main_menu(language: str = "en") -> InlineKeyboardMarkup:
    return _main_menu(language, direct_file=False)


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
        rows.append([InlineKeyboardButton(text=f"💬 {label} {display}", url=url)])
    back = BACK_LABELS.get(language, BACK_LABELS["en"])
    rows.append([button(back, "menu:back", style=ButtonStyle.PRIMARY, emoji_key="BACK")])
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
                    emoji_key="SPLIT",
                )
            ],
            [
                button(
                    text=messages["btn_quantity"],
                    action="split_type:quantity",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="SPLIT",
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


def quick_action_menu(language: str = "en") -> InlineKeyboardMarkup:
    return _main_menu(language, direct_file=True)


def file_split_result_menu(
    total: int, split: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    messages = SPLIT_MESSAGES.get(language, SPLIT_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(messages["btn_total"], "split:result:noop"),
                button(str(total), "split:result:noop"),
            ],
            [
                button(messages["btn_split"], "split:result:noop"),
                button(str(split), "split:result:noop"),
            ],
            [
                button(messages["btn_failed"], "split:result:noop"),
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
                InlineKeyboardButton(
                    text=msgs["btn_multi_type"],
                    callback_data="merge_type:multi_type",
                )
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_session_json_tdata"],
                    callback_data="merge_type:session_json_tdata",
                )
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_cancel"],
                    callback_data="action:cancel",
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
                button(f"{msgs['btn_total']}", "file_merge:noop"),
                button(f"{total}", "file_merge:noop"),
            ],
            [
                button(f"{msgs['btn_merged']}", "file_merge:noop"),
                button(f"{merged}", "file_merge:noop"),
            ],
            [
                button(f"{msgs['btn_error']}", "file_merge:noop"),
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
            button(f"🔨 {msgs['btn_total']}", "two_factor:noop"),
            button(str(total), "two_factor:noop"),
        ],
        [
            button(f"🔨 {msgs['btn_success']}", "two_factor:noop"),
            button(str(success), "two_factor:noop"),
        ],
        [
            button(f"🔨 {msgs['btn_failed']}", "two_factor:noop"),
            button(str(failed), "two_factor:noop"),
        ],
    ]
    if pending:
        rows.insert(
            2,
            [
                button(f"⏳ {msgs['btn_pending']}", "two_factor:noop"),
                button(str(pending), "two_factor:noop"),
            ],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_result_menu(
    total: int, success: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    from app.locales import CHANNEL_MESSAGES

    msgs = CHANNEL_MESSAGES.get(language, CHANNEL_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(f"🔨 {msgs['btn_total']}", "channel:noop"),
                button(str(total), "channel:noop"),
            ],
            [
                button(f"🔨 {msgs['btn_success']}", "channel:noop"),
                button(str(success), "channel:noop"),
            ],
            [
                button(f"🔨 {msgs['btn_failed']}", "channel:noop"),
                button(str(failed), "channel:noop"),
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
    rows.append([InlineKeyboardButton(text="🚀 /start", callback_data=start_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def membership_menu(
    channels: tuple[str, ...], language: str = "en"
) -> InlineKeyboardMarkup:
    locale = get_locale(language)
    rows = []
    for index, channel in enumerate(channels, start=1):
        if channel.startswith("@"):
            rows.append(
                [
                    InlineKeyboardButton(
                        text=(
                            locale.join_channel
                            if len(channels) == 1
                            else f"{locale.join_channel} {index}"
                        ),
                        url=f"https://t.me/{channel[1:]}",
                    ),
                    InlineKeyboardButton(
                        text=locale.joined,
                        callback_data=f"membership:check:{language}",
                    ),
                ]
            )
    if not rows:
        rows.append(
            [
                InlineKeyboardButton(
                    text=locale.joined,
                    callback_data=f"membership:check:{language}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def otp_initial_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = READ_OTP_MESSAGES.get(language, READ_OTP_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=msgs["btn_check"], callback_data="otp:check")],
            [InlineKeyboardButton(text=msgs["btn_skip"], callback_data="otp:skip")],
            [
                InlineKeyboardButton(
                    text=CANCEL_LABELS.get(language, CANCEL_LABELS["en"]),
                    callback_data="action:cancel",
                )
            ],
        ]
    )


def otp_checked_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = READ_OTP_MESSAGES.get(language, READ_OTP_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=msgs["btn_check_again"], callback_data="otp:check_again"
                )
            ],
            [
                InlineKeyboardButton(text=msgs["btn_skip"], callback_data="otp:skip"),
            ],
            [
                InlineKeyboardButton(
                    text=CANCEL_LABELS.get(language, CANCEL_LABELS["en"]),
                    callback_data="action:cancel",
                )
            ],
        ]
    )


def contacts_result_menu(
    checked: int, ok: int, error: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = CHECK_CONTACTS_MESSAGES.get(language, CHECK_CONTACTS_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=msgs["checked"], callback_data="contacts_stat:noop"
                ),
                InlineKeyboardButton(
                    text=str(checked), callback_data="contacts_stat:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["ok"], callback_data="contacts_stat:noop"
                ),
                InlineKeyboardButton(text=str(ok), callback_data="contacts_stat:noop"),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["error"], callback_data="contacts_stat:noop"
                ),
                InlineKeyboardButton(
                    text=str(error), callback_data="contacts_stat:noop"
                ),
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
                InlineKeyboardButton(
                    text=msgs["btn_total"], callback_data="account_txt:noop"
                ),
                InlineKeyboardButton(text=str(total), callback_data="account_txt:noop"),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_converted"], callback_data="account_txt:noop"
                ),
                InlineKeyboardButton(
                    text=str(converted), callback_data="account_txt:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_failed"], callback_data="account_txt:noop"
                ),
                InlineKeyboardButton(
                    text=str(failed), callback_data="account_txt:noop"
                ),
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
                InlineKeyboardButton(
                    text=msgs["btn_total"], callback_data="session_json:noop"
                ),
                InlineKeyboardButton(
                    text=str(total), callback_data="session_json:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_converted"], callback_data="session_json:noop"
                ),
                InlineKeyboardButton(
                    text=str(converted), callback_data="session_json:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_failed"], callback_data="session_json:noop"
                ),
                InlineKeyboardButton(
                    text=str(failed), callback_data="session_json:noop"
                ),
            ],
        ]
    )


def clear_contacts_result_menu(
    total: int, cleared: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = CLEAR_CONTACTS_MESSAGES.get(language, CLEAR_CONTACTS_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=msgs["btn_total"], callback_data="clear_contact:noop"
                ),
                InlineKeyboardButton(
                    text=str(total), callback_data="clear_contact:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_success"], callback_data="clear_contact:noop"
                ),
                InlineKeyboardButton(
                    text=str(cleared), callback_data="clear_contact:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_failed"], callback_data="clear_contact:noop"
                ),
                InlineKeyboardButton(
                    text=str(failed), callback_data="clear_contact:noop"
                ),
            ],
        ]
    )


def kill_sessions_confirm_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = KILL_SESSIONS_MESSAGES.get(language, KILL_SESSIONS_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=msgs["confirm_btn"],
                    callback_data="kill_sess:confirm",
                )
            ],
            [
                InlineKeyboardButton(
                    text=cancel_label,
                    callback_data="menu:back",
                )
            ],
        ]
    )


def kill_sessions_result_menu(
    total: int, killed: int, fresh: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = KILL_SESSIONS_MESSAGES.get(language, KILL_SESSIONS_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=msgs["btn_total"], callback_data="kill_sess:noop"
                ),
                InlineKeyboardButton(
                    text=str(total), callback_data="kill_sess:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_killed"], callback_data="kill_sess:noop"
                ),
                InlineKeyboardButton(
                    text=str(killed), callback_data="kill_sess:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_fresh"], callback_data="kill_sess:noop"
                ),
                InlineKeyboardButton(
                    text=str(fresh), callback_data="kill_sess:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_failed"], callback_data="kill_sess:noop"
                ),
                InlineKeyboardButton(
                    text=str(failed), callback_data="kill_sess:noop"
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
                InlineKeyboardButton(
                    text=msgs["skip_2fa"],
                    callback_data="fresh_sess:skip_2fa",
                )
            ],
            [
                InlineKeyboardButton(
                    text=cancel_label,
                    callback_data="menu:back",
                )
            ],
        ]
    )


def fresh_session_confirm_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = FRESH_SESSION_MESSAGES.get(language, FRESH_SESSION_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=msgs["confirm_btn"],
                    callback_data="fresh_sess:confirm",
                )
            ],
            [
                InlineKeyboardButton(
                    text=cancel_label,
                    callback_data="menu:back",
                )
            ],
        ]
    )


def fresh_session_result_menu(
    total: int, succeeded: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = FRESH_SESSION_MESSAGES.get(language, FRESH_SESSION_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=msgs["btn_total"], callback_data="fresh_sess:noop"
                ),
                InlineKeyboardButton(
                    text=str(total), callback_data="fresh_sess:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_ok"], callback_data="fresh_sess:noop"
                ),
                InlineKeyboardButton(
                    text=str(succeeded), callback_data="fresh_sess:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_failed"], callback_data="fresh_sess:noop"
                ),
                InlineKeyboardButton(
                    text=str(failed), callback_data="fresh_sess:noop"
                ),
            ],
        ]
    )


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

    def category_button(index: int) -> InlineKeyboardButton:
        category = categories[index]
        marker = "✅" if category in selected_set else "▫️"
        return button(f"{marker} {labels[index]}", f"clean_chat_toggle:{category}")

    all_selected = selected_set == set(categories)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [category_button(0), category_button(1)],
            [category_button(2), category_button(3)],
            [
                button(
                    actions["clear_all"] if all_selected else actions["select_all"],
                    "clean_chat_toggle:all",
                )
            ],
            [button(actions["confirm"], "clean_chat_confirm")],
            [button(cancel_label, "action:cancel")],
        ]
    )


def clean_chat_result_menu(
    total: int, cleaned: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = CLEAN_CHAT_MESSAGES.get(language, CLEAN_CHAT_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=msgs["btn_total"], callback_data="clean_chat:noop"
                ),
                InlineKeyboardButton(text=str(total), callback_data="clean_chat:noop"),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_success"], callback_data="clean_chat:noop"
                ),
                InlineKeyboardButton(
                    text=str(cleaned), callback_data="clean_chat:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_failed"], callback_data="clean_chat:noop"
                ),
                InlineKeyboardButton(text=str(failed), callback_data="clean_chat:noop"),
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
        prefix = "☑️" if is_selected else "◻️"
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
                    text=display_str, callback_data=f"del_cnt_toggle:{uid}"
                )
            ]
        )

    # Navigation row
    prev_btn = InlineKeyboardButton(
        text="⬅️" if page > 0 else " ",
        callback_data=f"del_cnt_page:{page - 1}" if page > 0 else "del_cnt:noop",
    )
    page_indicator = InlineKeyboardButton(
        text=f"📄 {page + 1}/{total_pages}", callback_data="del_cnt:noop"
    )
    next_btn = InlineKeyboardButton(
        text="➡️" if page < total_pages - 1 else " ",
        callback_data=f"del_cnt_page:{page + 1}"
        if page < total_pages - 1
        else "del_cnt:noop",
    )
    rows.append([prev_btn, page_indicator, next_btn])

    # Action row (Select All / Deselect All)
    rows.append(
        [
            InlineKeyboardButton(
                text=msgs["select_all"], callback_data="del_cnt_action:select_all"
            ),
            InlineKeyboardButton(
                text=msgs["deselect_all"], callback_data="del_cnt_action:deselect_all"
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
            )
        ]
    )

    # Cancel row
    rows.append([button(cancel_label, "action:cancel")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_contact_result_menu(
    total: int, deleted: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = DELETE_CONTACT_MESSAGES.get(language, DELETE_CONTACT_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=msgs["btn_total"], callback_data="del_cnt:noop"
                ),
                InlineKeyboardButton(text=str(total), callback_data="del_cnt:noop"),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_deleted"], callback_data="del_cnt:noop"
                ),
                InlineKeyboardButton(text=str(deleted), callback_data="del_cnt:noop"),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_failed"], callback_data="del_cnt:noop"
                ),
                InlineKeyboardButton(text=str(failed), callback_data="del_cnt:noop"),
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
                button(msgs["btn_edit_name"], "prof_setup:edit_name"),
                button(msgs["btn_edit_username"], "prof_setup:edit_username"),
            ],
            [
                button(msgs["btn_edit_about"], "prof_setup:edit_about"),
                button(msgs["btn_set_photo"], "prof_setup:set_photo"),
            ],
            [
                button(msgs["btn_apply"], "prof_setup:apply"),
            ],
            [
                button(msgs["btn_skip"], "prof_setup:skip"),
            ],
            [
                button(cancel_label, "flow:cancel"),
            ],
        ]
    )


def profile_setup_result_menu(
    total: int, modified: int, skipped: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = PROFILE_SETUP_MESSAGES.get(language, PROFILE_SETUP_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=msgs["btn_total"], callback_data="prof_setup:noop"
                ),
                InlineKeyboardButton(text=str(total), callback_data="prof_setup:noop"),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_modified"], callback_data="prof_setup:noop"
                ),
                InlineKeyboardButton(
                    text=str(modified), callback_data="prof_setup:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_skipped"], callback_data="prof_setup:noop"
                ),
                InlineKeyboardButton(
                    text=str(skipped), callback_data="prof_setup:noop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_failed"], callback_data="prof_setup:noop"
                ),
                InlineKeyboardButton(text=str(failed), callback_data="prof_setup:noop"),
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
    rows: list[list[InlineKeyboardButton]] = []

    if total_pages > 1:
        nav_row: list[InlineKeyboardButton] = []
        if total_pages > 5:
            nav_row.append(
                InlineKeyboardButton(
                    text="⏮" if page > 0 else " ",
                    callback_data="acc_age_page:0" if page > 0 else "acc_age:noop",
                )
            )

        nav_row.append(
            InlineKeyboardButton(
                text="◀️ Prev" if page > 0 else " ",
                callback_data=f"acc_age_page:{page - 1}"
                if page > 0
                else "acc_age:noop",
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
                text="Next ▶️" if page < total_pages - 1 else " ",
                callback_data=f"acc_age_page:{page + 1}"
                if page < total_pages - 1
                else "acc_age:noop",
            )
        )

        if total_pages > 5:
            nav_row.append(
                InlineKeyboardButton(
                    text="⏭" if page < total_pages - 1 else " ",
                    callback_data=f"acc_age_page:{total_pages - 1}"
                    if page < total_pages - 1
                    else "acc_age:noop",
                )
            )

        rows.append(nav_row)

    rows.append(
        [
            InlineKeyboardButton(text=msgs["btn_total"], callback_data="acc_age:noop"),
            InlineKeyboardButton(text=str(total), callback_data="acc_age:noop"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=msgs["btn_checked"], callback_data="acc_age:noop"
            ),
            InlineKeyboardButton(text=str(checked), callback_data="acc_age:noop"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(text=msgs["btn_failed"], callback_data="acc_age:noop"),
            InlineKeyboardButton(text=str(failed), callback_data="acc_age:noop"),
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
                InlineKeyboardButton(
                    text=msgs["btn_use_contacts"],
                    callback_data="mass_msg_recipients:contacts",
                )
            ],
            [
                InlineKeyboardButton(
                    text=cancel_label,
                    callback_data="action:cancel",
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
                InlineKeyboardButton(
                    text=msgs["btn_delay_fast"],
                    callback_data="mass_msg_delay:10_20",
                )
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_delay_balanced"],
                    callback_data="mass_msg_delay:20_60",
                )
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_delay_safe"],
                    callback_data="mass_msg_delay:60_120",
                )
            ],
            [
                InlineKeyboardButton(
                    text=cancel_label,
                    callback_data="action:cancel",
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
                InlineKeyboardButton(
                    text=msgs["btn_start"],
                    callback_data="mass_msg_action:start",
                )
            ],
            [
                InlineKeyboardButton(
                    text=cancel_label,
                    callback_data="action:cancel",
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
        InlineKeyboardButton(
            text=msgs["btn_resume"],
            callback_data="mass_msg_ctrl:resume",
        )
        if is_paused
        else InlineKeyboardButton(
            text=msgs["btn_pause"],
            callback_data="mass_msg_ctrl:pause",
        )
    )
    stop_btn = InlineKeyboardButton(
        text=msgs["btn_stop"],
        callback_data="mass_msg_ctrl:stop",
    )
    return InlineKeyboardMarkup(inline_keyboard=[[pause_resume_btn, stop_btn]])


def mass_message_paused_menu(
    job_id: str, language: str = "en"
) -> InlineKeyboardMarkup:
    from app.locales import MASS_MESSAGE_MESSAGES

    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=msgs["btn_resume"],
                    callback_data=f"resume_job:{job_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=cancel_label,
                    callback_data="menu:back",
                )
            ],
        ]
    )


def list_checker_cancel_menu(language: str = "en") -> InlineKeyboardMarkup:
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=cancel_label, callback_data="action:cancel")]]
    )


def list_checker_result_menu(
    tdata: int, session: int, json_cnt: int, total: int, language: str = "en"
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button("📁 Tdata", "list_check:noop"),
                button(str(tdata), "list_check:noop"),
            ],
            [
                button("🔑 Session", "list_check:noop"),
                button(str(session), "list_check:noop"),
            ],
            [
                button("📄 JSON", "list_check:noop"),
                button(str(json_cnt), "list_check:noop"),
            ],
            [
                button("✅ Total", "list_check:noop"),
                button(str(total), "list_check:noop"),
            ],
        ]
    )


def privacy_2fa_menu(language: str = "en") -> InlineKeyboardMarkup:
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [button("⏩ Skip", "privacy:skip_2fa")],
            [button(cancel_label, "action:cancel")],
        ]
    )


def privacy_mode_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [button(msgs["btn_preset"], "privacy:mode:preset")],
            [button(msgs["btn_custom"], "privacy:mode:custom")],
            [button(cancel_label, "action:cancel")],
        ]
    )


def privacy_presets_menu(language: str = "en") -> InlineKeyboardMarkup:
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    presets = msgs["presets"]
    back_label = BACK_LABELS.get(language, BACK_LABELS["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [button(presets["maximum"], "privacy:preset:maximum")],
            [button(presets["medium"], "privacy:preset:medium")],
            [button(presets["open"], "privacy:preset:open")],
            [button(back_label, "privacy:back_mode")],
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
        rows.append([button(f"{name}: {val_name}", f"privacy:rule:{key}")])

    rows.append([button(msgs["btn_apply_custom"], "privacy:apply_custom")])
    rows.append([button(back_label, "privacy:back_mode")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def privacy_value_menu(language: str = "en", rule_key: str = "") -> InlineKeyboardMarkup:
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    values_dict = msgs["values"]
    back_label = BACK_LABELS.get(language, BACK_LABELS["en"])

    rows = [
        [button(values_dict["everybody"], f"privacy:val:{rule_key}:everybody")],
        [button(values_dict["contacts"], f"privacy:val:{rule_key}:contacts")],
        [button(values_dict["nobody"], f"privacy:val:{rule_key}:nobody")],
        [button(back_label, "privacy:back_custom")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def privacy_result_menu(
    total: int, succeeded: int, failed: int, language: str = "en"
) -> InlineKeyboardMarkup:
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(msgs["btn_total"], "privacy:noop"),
                button(str(total), "privacy:noop"),
            ],
            [
                button(msgs["btn_ok"], "privacy:noop"),
                button(str(succeeded), "privacy:noop"),
            ],
            [
                button(msgs["btn_failed"], "privacy:noop"),
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
        [button(l["set"], "proxy:set")],
        [button(l["view"], "proxy:view")],
    ]
    if has_proxy:
        rows.append([button(l["remove"], "proxy:remove")])
    rows.append([button(l["back"], "menu:back")])
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




