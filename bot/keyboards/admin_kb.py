"""Inline keyboards for administrator dashboard and all modular sections."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models.group_settings import GroupSettings


def get_admin_dashboard_keyboard(group_id: int, settings: GroupSettings) -> InlineKeyboardMarkup:
    """Constructs the comprehensive modular admin control panel keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(text="🎯 Referrals", callback_data=f"adm_sec:ref:{group_id}"),
            InlineKeyboardButton(text="🔨 Moderation", callback_data=f"adm_sec:mod:{group_id}")
        ],
        [
            InlineKeyboardButton(text="👑 Staff & Roles", callback_data=f"adm_sec:staff:{group_id}"),
            InlineKeyboardButton(text="👥 Members", callback_data=f"adm_sec:members:{group_id}")
        ],
        [
            InlineKeyboardButton(text="🔒 Locks", callback_data=f"adm_sec:locks:{group_id}"),
            InlineKeyboardButton(text="🚫 Banned Words", callback_data=f"adm_sec:words:{group_id}")
        ],
        [
            InlineKeyboardButton(text="🔗 Link Filter", callback_data=f"adm_sec:links:{group_id}"),
            InlineKeyboardButton(text="🛡 Anti-Spam", callback_data=f"adm_sec:spam:{group_id}")
        ],
        [
            InlineKeyboardButton(text="🚨 Anti-Raid", callback_data=f"adm_sec:raid:{group_id}"),
            InlineKeyboardButton(text="🤖 Captcha", callback_data=f"adm_sec:captcha:{group_id}")
        ],
        [
            InlineKeyboardButton(text="👋 Welcome/Goodbye", callback_data=f"adm_sec:welc:{group_id}"),
            InlineKeyboardButton(text="🗑 Auto-Delete", callback_data=f"adm_sec:autodel:{group_id}")
        ],
        [
            InlineKeyboardButton(text="📊 Statistics", callback_data=f"adm_sec:stats:{group_id}"),
            InlineKeyboardButton(text="🏆 Top Chatters", callback_data=f"adm_sec:top:{group_id}")
        ],
        [
            InlineKeyboardButton(text="📜 Rules", callback_data=f"adm_view_rules:{group_id}"),
            InlineKeyboardButton(text="📋 Recent Logs", callback_data=f"adm_sec:logs:{group_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Close Dashboard", callback_data=f"adm_close:{group_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_referral_settings_keyboard(group_id: int, settings: GroupSettings) -> InlineKeyboardMarkup:
    """Settings submenu for referral system."""
    ref_btn = "🟢 Referral: ON" if settings.referral_enabled else "🔴 Referral: OFF"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=ref_btn, callback_data=f"adm_tgl_ref:{group_id}")],
            [
                InlineKeyboardButton(text=f"⏳ Deadline: {settings.referral_deadline_hours}h", callback_data=f"adm_menu_deadline:{group_id}"),
                InlineKeyboardButton(text=f"🎯 Required: {settings.required_referrals}", callback_data=f"adm_menu_req:{group_id}")
            ],
            [
                InlineKeyboardButton(text=f"⚡ Failure Action: {settings.failure_action}", callback_data=f"adm_menu_action:{group_id}")
            ],
            [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data=f"adm_back:{group_id}")]
        ]
    )


def get_deadline_options_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Options for setting referral deadline."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 Hour", callback_data=f"adm_set_dl:{group_id}:1"),
                InlineKeyboardButton(text="6 Hours", callback_data=f"adm_set_dl:{group_id}:6"),
                InlineKeyboardButton(text="12 Hours", callback_data=f"adm_set_dl:{group_id}:12")
            ],
            [
                InlineKeyboardButton(text="24 Hours", callback_data=f"adm_set_dl:{group_id}:24"),
                InlineKeyboardButton(text="48 Hours", callback_data=f"adm_set_dl:{group_id}:48")
            ],
            [InlineKeyboardButton(text="🔙 Back", callback_data=f"adm_sec:ref:{group_id}")]
        ]
    )


def get_required_referrals_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Options for setting required referral count."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 Referral", callback_data=f"adm_set_req:{group_id}:1"),
                InlineKeyboardButton(text="2 Referrals", callback_data=f"adm_set_req:{group_id}:2"),
                InlineKeyboardButton(text="3 Referrals", callback_data=f"adm_set_req:{group_id}:3")
            ],
            [InlineKeyboardButton(text="🔙 Back", callback_data=f"adm_sec:ref:{group_id}")]
        ]
    )


def get_failure_action_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Options for failure action."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚫 Kick", callback_data=f"adm_set_act:{group_id}:KICK"),
                InlineKeyboardButton(text="🔇 Restrict", callback_data=f"adm_set_act:{group_id}:RESTRICT"),
                InlineKeyboardButton(text="🆓 None", callback_data=f"adm_set_act:{group_id}:NONE")
            ],
            [InlineKeyboardButton(text="🔙 Back", callback_data=f"adm_sec:ref:{group_id}")]
        ]
    )


def get_back_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data=f"adm_back:{group_id}")]
        ]
    )
