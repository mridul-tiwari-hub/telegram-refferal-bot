"""Moderation Commands Handlers."""
from typing import Optional
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.group_repo import GroupRepository
from database.repositories.user_repo import UserRepository
from services.moderation_service import ModerationService
from services.warning_service import WarningService
from bot.filters.admin_filter import IsAdminFilter

moderation_router = Router(name="moderation_router")
moderation_router.message.filter(IsAdminFilter())


@moderation_router.message(Command("warn"))
async def handle_warn(message: Message, session: AsyncSession) -> None:
    """Issues a warning to a member."""
    args = message.text.split(maxsplit=2)
    target_tg_id: Optional[int] = None
    reason = "Violating group rules"

    if message.reply_to_message and message.reply_to_message.from_user:
        target_tg_id = message.reply_to_message.from_user.id
        if len(args) > 1:
            reason = " ".join(args[1:])
    elif len(args) > 1:
        try:
            target_tg_id = int(args[1])
            if len(args) > 2:
                reason = args[2]
        except ValueError:
            pass

    if not target_tg_id:
        await message.answer("Usage: <code>/warn &lt;USER_ID&gt; [REASON]</code> or reply to a message.", parse_mode="HTML")
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    warning_service = WarningService(session, message.bot)

    group = await group_repo.get_by_telegram_id(message.chat.id)
    user = await user_repo.get_or_create_user(telegram_user_id=target_tg_id)
    admin = await user_repo.get_by_telegram_id(message.from_user.id)

    warning, count, limit, action_triggered = await warning_service.issue_warning(
        group=group,
        user=user,
        admin_user_id=admin.id if admin else None,
        reason=reason
    )

    action_text = f"\n🚨 <b>Limit reached! Moderation action executed.</b>" if action_triggered else ""
    await message.answer(
        f"⚠️ <b>Warning Issued!</b>\n"
        f"• User: <code>{user.telegram_user_id}</code>\n"
        f"• Reason: <i>{reason}</i>\n"
        f"• Warnings: <b>{count}/{limit}</b>{action_text}",
        parse_mode="HTML"
    )


@moderation_router.message(Command("warnings"))
async def handle_warnings(message: Message, session: AsyncSession) -> None:
    """Views warnings for a user."""
    args = message.text.split()[1:]
    target_tg_id: Optional[int] = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_tg_id = message.reply_to_message.from_user.id
    elif args:
        try:
            target_tg_id = int(args[0])
        except ValueError:
            pass

    if not target_tg_id:
        await message.answer("Usage: <code>/warnings &lt;USER_ID&gt;</code> or reply to a message.", parse_mode="HTML")
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    warning_service = WarningService(session, message.bot)

    group = await group_repo.get_by_telegram_id(message.chat.id)
    user = await user_repo.get_by_telegram_id(target_tg_id)

    if not group or not user:
        await message.answer("User or group record not found.")
        return

    warnings = await warning_service.get_user_warnings(group.id, user.id)
    if not warnings:
        await message.answer(f"User <code>{user.telegram_user_id}</code> has 0 active warnings.", parse_mode="HTML")
        return

    lines = [f"⚠️ <b>Warnings for {user.telegram_user_id} ({len(warnings)} total):</b>\n"]
    for idx, w in enumerate(warnings, 1):
        lines.append(f"{idx}. {w.reason} ({w.created_at.strftime('%Y-%m-%d %H:%M')})")

    await message.answer("\n".join(lines), parse_mode="HTML")


@moderation_router.message(Command("resetwarnings"))
async def handle_resetwarnings(message: Message, session: AsyncSession) -> None:
    """Resets all warnings for a user."""
    args = message.text.split()[1:]
    target_tg_id: Optional[int] = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_tg_id = message.reply_to_message.from_user.id
    elif args:
        try:
            target_tg_id = int(args[0])
        except ValueError:
            pass

    if not target_tg_id:
        await message.answer("Usage: <code>/resetwarnings &lt;USER_ID&gt;</code>", parse_mode="HTML")
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    warning_service = WarningService(session, message.bot)

    group = await group_repo.get_by_telegram_id(message.chat.id)
    user = await user_repo.get_by_telegram_id(target_tg_id)
    admin = await user_repo.get_by_telegram_id(message.from_user.id)

    if not group or not user:
        await message.answer("User or group record not found.")
        return

    cleared = await warning_service.reset_user_warnings(group.id, user.id, admin.id if admin else None)
    await message.answer(f"✅ Cleared <b>{cleared}</b> warnings for user <code>{user.telegram_user_id}</code>.", parse_mode="HTML")


@moderation_router.message(Command("remove"))
async def handle_remove(message: Message, session: AsyncSession) -> None:
    """Kicks a member (ban followed by unban so they can rejoin)."""
    args = message.text.split()[1:]
    target_tg_id: Optional[int] = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_tg_id = message.reply_to_message.from_user.id
    elif args:
        try:
            target_tg_id = int(args[0])
        except ValueError:
            pass

    if not target_tg_id:
        await message.answer("Usage: <code>/remove &lt;USER_ID&gt;</code> or reply to a message.", parse_mode="HTML")
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    mod_service = ModerationService(session, message.bot)

    group = await group_repo.get_by_telegram_id(message.chat.id)
    user = await user_repo.get_or_create_user(telegram_user_id=target_tg_id)
    admin = await user_repo.get_by_telegram_id(message.from_user.id)

    success = await mod_service.kick_member(
        group=group,
        user=user,
        admin_user_id=admin.id if admin else None,
        reason="Manual removal by administrator"
    )
    if success:
        await message.answer(f"🚫 Kicked user <code>{user.telegram_user_id}</code> from the group.", parse_mode="HTML")
    else:
        await message.answer("Failed to kick user. Please ensure the bot has administrator privileges.")


@moderation_router.message(Command("restrict"))
async def handle_restrict(message: Message, session: AsyncSession) -> None:
    """Restricts a member's chat permissions."""
    args = message.text.split()[1:]
    target_tg_id: Optional[int] = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_tg_id = message.reply_to_message.from_user.id
    elif args:
        try:
            target_tg_id = int(args[0])
        except ValueError:
            pass

    if not target_tg_id:
        await message.answer("Usage: <code>/restrict &lt;USER_ID&gt;</code> or reply to a message.", parse_mode="HTML")
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    mod_service = ModerationService(session, message.bot)

    group = await group_repo.get_by_telegram_id(message.chat.id)
    user = await user_repo.get_or_create_user(telegram_user_id=target_tg_id)
    admin = await user_repo.get_by_telegram_id(message.from_user.id)

    success = await mod_service.restrict_member(
        group=group,
        user=user,
        admin_user_id=admin.id if admin else None,
        reason="Manual restriction by administrator"
    )
    if success:
        await message.answer(f"🔇 Restricted user <code>{user.telegram_user_id}</code>.", parse_mode="HTML")
    else:
        await message.answer("Failed to restrict user. Please check bot permissions.")


@moderation_router.message(Command("unrestrict"))
async def handle_unrestrict(message: Message, session: AsyncSession) -> None:
    """Restores a member's chat permissions."""
    args = message.text.split()[1:]
    target_tg_id: Optional[int] = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_tg_id = message.reply_to_message.from_user.id
    elif args:
        try:
            target_tg_id = int(args[0])
        except ValueError:
            pass

    if not target_tg_id:
        await message.answer("Usage: <code>/unrestrict &lt;USER_ID&gt;</code> or reply to a message.", parse_mode="HTML")
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    mod_service = ModerationService(session, message.bot)

    group = await group_repo.get_by_telegram_id(message.chat.id)
    user = await user_repo.get_or_create_user(telegram_user_id=target_tg_id)
    admin = await user_repo.get_by_telegram_id(message.from_user.id)

    success = await mod_service.unrestrict_member(
        group=group,
        user=user,
        admin_user_id=admin.id if admin else None
    )
    if success:
        await message.answer(f"🔊 Restored permissions for user <code>{user.telegram_user_id}</code>.", parse_mode="HTML")
    else:
        await message.answer("Failed to unrestrict user.")
