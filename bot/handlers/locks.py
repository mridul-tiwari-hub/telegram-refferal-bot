"""Group Content Locks Handlers."""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.group_repo import GroupRepository
from database.repositories.admin_repo import AdminRepository
from services.permission_service import PermissionService
from utils.logging import get_logger

logger = get_logger(__name__)
locks_router = Router(name="locks_router")

LOCK_TYPE_MAP = {
    "all": "lock_all",
    "text": "lock_text",
    "photo": "lock_photos",
    "photos": "lock_photos",
    "video": "lock_videos",
    "videos": "lock_videos",
    "sticker": "lock_stickers",
    "stickers": "lock_stickers",
    "gif": "lock_gifs",
    "gifs": "lock_gifs",
    "voice": "lock_voice",
    "audio": "lock_audio",
    "document": "lock_documents",
    "documents": "lock_documents",
    "file": "lock_documents",
    "link": "lock_links",
    "links": "lock_links",
    "poll": "lock_polls",
    "polls": "lock_polls"
}


@locks_router.message(Command("lock"))
async def handle_lock(message: Message, session: AsyncSession) -> None:
    """Locks a content type in the group."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="locks",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    tokens = message.text.split()
    if len(tokens) < 2 or tokens[1].lower() not in LOCK_TYPE_MAP:
        valid_types = ", ".join(["all", "text", "photo", "video", "sticker", "gif", "voice", "audio", "document", "link", "poll"])
        await message.answer(f"Usage: <code>/lock &lt;TYPE&gt;</code>\nValid types: <code>{valid_types}</code>", parse_mode="HTML")
        return

    lock_type = tokens[1].lower()
    attr_name = LOCK_TYPE_MAP[lock_type]

    await admin_repo.update_locks(group.id, **{attr_name: True})
    await perm_service.log_action(
        group=group,
        actor_tg_id=message.from_user.id,
        action="LOCK",
        details=f"Type: {lock_type}"
    )
    await message.answer(f"🔒 <b>{lock_type.upper()}</b> has been locked for ordinary members.", parse_mode="HTML")


@locks_router.message(Command("unlock"))
async def handle_unlock(message: Message, session: AsyncSession) -> None:
    """Unlocks a content type in the group."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="locks",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    tokens = message.text.split()
    if len(tokens) < 2 or tokens[1].lower() not in LOCK_TYPE_MAP:
        valid_types = ", ".join(["all", "text", "photo", "video", "sticker", "gif", "voice", "audio", "document", "link", "poll"])
        await message.answer(f"Usage: <code>/unlock &lt;TYPE&gt;</code>\nValid types: <code>{valid_types}</code>", parse_mode="HTML")
        return

    lock_type = tokens[1].lower()
    attr_name = LOCK_TYPE_MAP[lock_type]

    await admin_repo.update_locks(group.id, **{attr_name: False})
    await perm_service.log_action(
        group=group,
        actor_tg_id=message.from_user.id,
        action="UNLOCK",
        details=f"Type: {lock_type}"
    )
    await message.answer(f"🔓 <b>{lock_type.upper()}</b> has been unlocked.", parse_mode="HTML")


@locks_router.message(Command("locks"))
async def handle_locks_status(message: Message, session: AsyncSession) -> None:
    """Displays current group locks."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    locks = await admin_repo.get_or_create_locks(group.id)

    def icon(val: bool) -> str:
        return "🔒 Locked" if val else "🔓 Open"

    text = (
        f"🔐 <b>GROUP CONTENT LOCKS — {group.group_name}</b>\n\n"
        f"• All: <b>{icon(locks.lock_all)}</b>\n"
        f"• Text: <b>{icon(locks.lock_text)}</b>\n"
        f"• Photos: <b>{icon(locks.lock_photos)}</b>\n"
        f"• Videos: <b>{icon(locks.lock_videos)}</b>\n"
        f"• Stickers: <b>{icon(locks.lock_stickers)}</b>\n"
        f"• GIFs: <b>{icon(locks.lock_gifs)}</b>\n"
        f"• Voice / Notes: <b>{icon(locks.lock_voice)}</b>\n"
        f"• Audio: <b>{icon(locks.lock_audio)}</b>\n"
        f"• Documents: <b>{icon(locks.lock_documents)}</b>\n"
        f"• Links: <b>{icon(locks.lock_links)}</b>\n"
        f"• Polls: <b>{icon(locks.lock_polls)}</b>\n\n"
        f"Use <code>/lock &lt;type&gt;</code> or <code>/unlock &lt;type&gt;</code> to manage."
    )
    await message.answer(text, parse_mode="HTML")
