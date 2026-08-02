from aiogram.fsm.state import State, StatesGroup


class AnalyzeFile(StatesGroup):
    waiting_for_file = State()


class SplitFile(StatesGroup):
    waiting_for_file = State()
    waiting_for_split_type = State()
    waiting_for_quantity = State()


class ReadOTP(StatesGroup):
    waiting_for_file = State()
    viewing_account = State()


class ConvertSessionToTdata(StatesGroup):
    waiting_for_file = State()


class ConvertTdataToSession(StatesGroup):
    waiting_for_file = State()


class AccountToTxt(StatesGroup):
    waiting_for_file = State()


class ConvertSessionToJson(StatesGroup):
    waiting_for_file = State()


class FileMerge(StatesGroup):
    waiting_for_file = State()
    waiting_for_merge_type = State()


class DirectFile(StatesGroup):
    waiting_for_action = State()


class Change2FA(StatesGroup):
    waiting_for_file = State()
    waiting_for_old_password = State()
    waiting_for_new_password = State()


class Disable2FA(StatesGroup):
    waiting_for_file = State()
    waiting_for_password = State()


class Reset2FA(StatesGroup):
    waiting_for_file = State()


class ChannelJoin(StatesGroup):
    waiting_for_file = State()
    waiting_for_target = State()


class ChannelLeave(StatesGroup):
    waiting_for_file = State()
    waiting_for_target = State()


class ClearContacts(StatesGroup):
    waiting_for_file = State()


class CleanChat(StatesGroup):
    waiting_for_file = State()
    waiting_for_selection = State()


class DeleteContact(StatesGroup):
    waiting_for_file = State()
    selecting_contacts = State()


class ProfileSetup(StatesGroup):
    waiting_for_file = State()
    managing_account = State()
    waiting_for_name = State()
    waiting_for_username = State()
    waiting_for_about = State()
    waiting_for_photo = State()


class AccountAge(StatesGroup):
    waiting_for_file = State()
    viewing_results = State()


class KillSessions(StatesGroup):
    waiting_for_file = State()
    confirming = State()


class FreshSession(StatesGroup):
    waiting_for_file = State()
    waiting_for_2fa = State()
    confirming = State()


class MassMessage(StatesGroup):
    waiting_for_file = State()
    waiting_for_recipients = State()
    waiting_for_content = State()
    configuring_delay = State()
    confirming = State()
    running = State()

