"""Inline keyboards for administrator dashboard and settings."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models.group_settings import GroupSettings


def get_admin_dashboard_keyboard(group_id: int, settings: GroupSettings) -> InlineKeyboardMarkup:
    """Constructs the main admin control panel keyboard."""
    ref_status_text = "🟢 Referral: ON" if settings.referral_enabled else "🔴 Referral: OFF"
    spam_status_text = "🟢 Anti-Spam: ON" if settings.anti_spam_enabled else "🔴 Anti-Spam: OFF"

    keyboard = [
        [
            InlineKeyboardButton(text=ref_status_text, callback_data=f"adm_tgl_ref:{group_id}"),
            InlineKeyboardButton(text=spam_status_text, callback_data=f"adm_tgl_spam:{group_id}")
        ],
        [
            InlineKeyboardButton(text=f"⏳ Deadline: {settings.referral_deadline_hours}h", callback_data=f"adm_menu_deadline:{group_id}"),
            InlineKeyboardButton(text=f"🎯 Required: {settings.required_referrals}", callback_data=f"adm_menu_req:{group_id}")
        ],
        [
            InlineKeyboardButton(text=f"⚡ Action: {settings.failure_action}", callback_data=f"adm_menu_action:{group_id}"),
            InlineKeyboardButton(text="📊 View Stats", callback_data=f"adm_stats:{group_id}")
        ],
        [
            InlineKeyboardButton(text="📜 Rules", callback_data=f"adm_view_rules:{group_id}"),
            InlineKeyboardButton(text="❌ Close Menu", callback_data=f"adm_close:{group_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_deadline_options_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Options for setting referral deadline."""
    keyboard = [
        [
            InlineKeyboardButton(text="1 Hour", callback_data=f"adm_set_dl:{group_id}:1"),
            InlineKeyboardButton(text="6 Hours", callback_data=f"adm_set_dl:{group_id}:6"),
            InlineKeyboardButton(text="12 Hours", callback_data=f"adm_set_dl:{group_id}:12")
        ],
        [
            InlineKeyboardButton(text="24 Hours", callback_data=f"adm_set_dl:{group_id}:24"),
            InlineKeyboardButton(text="48 Hours", callback_data=f"adm_set_dl:{group_id}:48")
        ],
        [
            InlineKeyboardButton(text="🔙 Back to Dashboard", callback_data=f"adm_back:{group_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_required_referrals_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Options for setting required referral count."""
    keyboard = [
        [
            InlineKeyboardButton(text="1 Referral", callback_data=f"adm_set_req:{group_id}:1"),
            InlineKeyboardButton(text="2 Referrals", callback_data=f"adm_set_req:{group_id}:2"),
            InlineKeyboardButton(text="3 Referrals", callback_data=f"adm_set_req:{group_id}:3")
        ],
        [
            InlineKeyboardButton(text="🔙 Back to Dashboard", callback_data=f"adm_back:{group_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_failure_action_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Options for failure action."""
    keyboard = [
        [
            InlineKeyboardButton(text="🚫 Kick", callback_data=f"adm_set_act:{group_id}:KICK"),
            InlineKeyboardButton(text="🔇 Restrict", callback_data=f"adm_set_act:{group_id}:RESTRICT"),
            InlineKeyboardButton(text="🆓 No Action", callback_data=f"adm_set_act:{group_id}:NONE")
        ],
        [
            InlineKeyboardButton(text="🔙 Back to Dashboard", callback_data=f"adm_back:{group_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
