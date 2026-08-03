"""app/admin/states.py — FSM State classes for Admin Panel interactive inputs."""

from aiogram.fsm.state import State, StatesGroup


class UserSearchState(StatesGroup):
    waiting_for_query = State()


class UserDirectMessageState(StatesGroup):
    waiting_for_message = State()


class BroadcastState(StatesGroup):
    waiting_for_content = State()
    waiting_for_preview_confirm = State()


class AddAdminState(StatesGroup):
    waiting_for_role = State()      # Inline role selection (set via FSM data, not a text state)
    waiting_for_user_id = State()   # After role selected, receive Telegram ID


class AddForceJoinState(StatesGroup):
    waiting_for_channel_info = State()


class SetSupportState(StatesGroup):
    waiting_for_support_id = State()


class AddVIPPlanState(StatesGroup):
    waiting_for_plan_details = State()  # Title, Months, Price


class PaymentSettingState(StatesGroup):
    waiting_for_wallets = State()
