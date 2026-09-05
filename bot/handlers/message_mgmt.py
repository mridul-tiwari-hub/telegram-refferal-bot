"""Message Management Handlers: Del, Purge, DelAll, and AutoDelete."""
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.group_repo import GroupRepository
from services.permission_service import PermissionService
from utils.logging import get_logger

logger = get_logger(__name__)
message_mgmt_router = Router(name="message_mgmt_router")


@message_mgmt_router.message(Command("del"))
async def handle_del(message: Message, session: AsyncSession) -> None:
    """Deletes replied message."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    if not message.reply_to_message:
        await message.answer("Reply to a message with <code>/del</code> to delete it.", parse_mode="HTML")
        return

    group_repo = GroupRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="delete",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    try:
        await message.reply_to_message.delete()
        await message.delete()
    except Exception as e:
        logger.debug(f"Failed to delete message: {e}")


@message_mgmt_router.message(Command("purge"))
async def handle_purge(message: Message, session: AsyncSession) -> None:
    """Purges recent messages up to specified count."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="delete",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    tokens = message.text.split()
    count = 10
    if len(tokens) > 1:
        try:
            count = min(int(tokens[1]), 100)
        except ValueError:
            pass

    current_id = message.message_id
    deleted = 0
    for mid in range(current_id, current_id - count - 1, -1):
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=mid)
            deleted += 1
        except Exception:
            pass

    notice = await message.answer(f"🗑 Purged <b>{deleted}</b> messages.", parse_mode="HTML")
    await asyncio.sleep(4)
    try:
        await notice.delete()
    except Exception:
        pass


@message_mgmt_router.message(Command("delall"))
async def handle_delall_prompt(message: Message, session: AsyncSession) -> None:
    """Prompts confirmation for large-scale message deletion."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="delete",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    confirm_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚠️ Yes, Delete Last 100 Messages", callback_data=f"delall_confirm:{group.id}:{message.from_user.id}"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="delall_cancel")
            ]
        ]
    )
    await message.answer("⚠️ <b>Confirm Bulk Message Deletion</b>\nAre you sure you want to delete the last 100 messages?", reply_markup=confirm_kb, parse_mode="HTML")


@message_mgmt_router.callback_query(F.data.startswith("delall_confirm:"))
async def handle_delall_execute(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    group_id = int(parts[1])
    owner_id = int(parts[2])

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Only the initiating admin can confirm.", show_alert=True)
        return

    current_id = callback.message.message_id
    deleted = 0
    for mid in range(current_id, current_id - 100, -1):
        try:
            await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=mid)
            deleted += 1
        except Exception:
            pass

    await callback.answer(f"Bulk deleted {deleted} messages.")


@message_mgmt_router.callback_query(F.data == "delall_cancel")
async def handle_delall_cancel(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer("Cancelled")


@message_mgmt_router.message(Command("autodelete"))
async def handle_autodelete(message: Message, session: AsyncSession) -> None:
    """Configures automatic deletion delay for group messages."""
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
        settings = await group_repo.get_settings(group.id)
        current = f"{settings.auto_delete_seconds}s" if settings.auto_delete_seconds > 0 else "DISABLED"
        await message.answer(f"Auto-delete is currently: <b>{current}</b>\nUsage: <code>/autodelete &lt;SECONDS&gt;</code> or <code>/autodelete off</code>", parse_mode="HTML")
        return

    val = tokens[1].lower()
    if val in ["off", "0", "disable", "disabled"]:
        await group_repo.update_settings(group.id, auto_delete_seconds=0)
        await message.answer("✅ Auto-delete has been disabled.", parse_mode="HTML")
        return

    try:
        secs = int(tokens[1])
        if secs < 10:
            await message.answer("Please specify at least 10 seconds.")
            return
        await group_repo.update_settings(group.id, auto_delete_seconds=secs)
        await message.answer(f"✅ Messages will now be auto-deleted after <b>{secs} seconds</b>.", parse_mode="HTML")
    except ValueError:
        await message.answer("Usage: <code>/autodelete &lt;SECONDS&gt;</code> or <code>/autodelete off</code>", parse_mode="HTML")
