"""Inline keyboards for regular user dashboards and pagination."""
from typing import Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_status_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Provides Refresh Status and Share Link buttons."""
    keyboard = [
        [
            InlineKeyboardButton(text="🔄 Refresh Status", callback_data=f"user_refresh_status:{group_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_start_bot_keyboard(bot_username: str, group_id: int) -> InlineKeyboardMarkup:
    """Allows new group members to start the bot in private DM to receive their personal invite link."""
    url = f"https://t.me/{bot_username}?start=ref_{group_id}"
    keyboard = [
        [
            InlineKeyboardButton(text="👉 Get My Personal Referral Link", url=url)
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_tree_pagination_keyboard(group_id: int, current_page: int, total_pages: int) -> Optional[InlineKeyboardMarkup]:
    """Provides next/prev pagination for large referral trees."""
    if total_pages <= 1:
        return None

    buttons = []
    if current_page > 1:
        buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"tree_page:{group_id}:{current_page - 1}"))
    if current_page < total_pages:
        buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"tree_page:{group_id}:{current_page + 1}"))

    return InlineKeyboardMarkup(inline_keyboard=[buttons])
