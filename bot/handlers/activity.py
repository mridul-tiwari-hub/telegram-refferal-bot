"""Activity, Group Info, and Log Channel Handlers."""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.group_repo import GroupRepository
from database.repositories.admin_repo import AdminRepository
from services.activity_service import ActivityService
from services.permission_service import PermissionService, UserRole
from utils.logging import get_logger

logger = get_logger(__name__)
activity_router = Router(name="activity_router")


@activity_router.message(Command("top"))
@activity_router.message(Command("topchat"))
async def handle_top(message: Message, session: AsyncSession) -> None:
    """Displays top chatters leaderboard."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    activity_service = ActivityService(session, message.bot)

    text = await activity_service.get_top_chatters_text(group.id, limit=10)
    await message.answer(text, parse_mode="HTML")


@activity_router.message(Command("inactive"))
async def handle_inactive(message: Message, session: AsyncSession) -> None:
    """Displays inactive members in the group."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="stats",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    tokens = message.text.split()
    days = 30
    if len(tokens) > 1:
        try:
            days = int(tokens[1])
        except ValueError:
            pass

    activity_service = ActivityService(session, message.bot)
    text = await activity_service.get_inactive_members_text(group.id, days=days)
    await message.answer(text, parse_mode="HTML")


@activity_router.message(Command("groupinfo"))
async def handle_groupinfo(message: Message, session: AsyncSession) -> None:
    """Displays real Telegram group metadata and bot configuration."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    settings = await group_repo.get_settings(group.id)

    member_count_str = "Unavailable"
    try:
        count = await message.bot.get_chat_member_count(message.chat.id)
        member_count_str = str(count)
    except Exception:
        pass

    text = (
        f"ℹ️ <b>GROUP INFORMATION — {group.group_name}</b>\n\n"
        f"• Group Title: <b>{message.chat.title}</b>\n"
        f"• Group ID: <code>{message.chat.id}</code>\n"
        f"• Group Type: <b>{message.chat.type.name}</b>\n"
        f"• Member Count: <b>{member_count_str}</b>\n\n"
        f"<b>Bot Configuration:</b>\n"
        f"• Referral System: <b>{'ENABLED' if settings.referral_enabled else 'DISABLED'}</b>\n"
        f"• Referral Deadline: <b>{settings.referral_deadline_hours}h</b>\n"
        f"• Required Referrals: <b>{settings.required_referrals}</b>\n"
        f"• Failure Action: <b>{settings.failure_action}</b>\n"
        f"• Anti-Spam: <b>{'ENABLED' if settings.anti_spam_enabled else 'DISABLED'}</b>\n"
        f"• Captcha: <b>{'ENABLED' if settings.captcha_enabled else 'DISABLED'}</b>\n"
        f"• Raid Mode: <b>{'ENABLED' if settings.raid_mode else 'DISABLED'}</b>\n"
        f"• Auto-Delete: <b>{settings.auto_delete_seconds}s</b>\n"
        f"• Link Filter Mode: <b>{settings.link_filter_mode}</b>\n"
        f"• Log Channel: <code>{settings.log_channel_id or 'None'}</code>"
    )
    await message.answer(text, parse_mode="HTML")


@activity_router.message(Command("setlogchannel"))
async def handle_setlogchannel(message: Message, session: AsyncSession) -> None:
    """Sets a dedicated moderation log channel for this group."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="settings",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    tokens = message.text.split()
    if len(tokens) < 2:
        await message.answer("Usage: <code>/setlogchannel &lt;CHANNEL_ID&gt;</code> or <code>/setlogchannel off</code>", parse_mode="HTML")
        return

    val = tokens[1].lower()
    if val in ["off", "none", "disable", "disabled"]:
        await group_repo.update_settings(group.id, log_channel_id=None)
        await message.answer("✅ Moderation log channel disabled for this group.", parse_mode="HTML")
        return

    try:
        channel_id = int(tokens[1])
        await group_repo.update_settings(group.id, log_channel_id=channel_id)
        await message.answer(f"✅ Moderation log channel set to <code>{channel_id}</code>.", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Invalid channel ID. Please provide numeric channel ID (e.g. -1001234567890).", parse_mode="HTML")
