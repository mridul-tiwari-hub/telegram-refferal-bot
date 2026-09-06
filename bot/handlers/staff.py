"""Staff Management Handlers."""
from typing import Optional
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.group_repo import GroupRepository
from database.repositories.user_repo import UserRepository
from database.repositories.admin_repo import AdminRepository
from services.permission_service import PermissionService, UserRole
from utils.logging import get_logger

logger = get_logger(__name__)
staff_router = Router(name="staff_router")


@staff_router.message(Command("addstaff"))
async def handle_addstaff(message: Message, session: AsyncSession) -> None:
    """Adds a staff member with specified permissions."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.answer("Please use this command inside a group.")
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    admin_repo = AdminRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    actor_role, _ = await perm_service.get_user_role_and_rank(message.chat.id, message.from_user.id, group.id)

    # Only Owner or Administrator can add staff
    if actor_role < UserRole.ADMIN:
        await message.answer("❌ Only Administrators or Group Owners can manage bot staff.")
        return

    args = message.text.split(maxsplit=2)
    target_tg_id: Optional[int] = None
    perms = "ban,mute,warn,delete,filters,locks,welcome,rules,stats,referrals,settings"

    if message.reply_to_message and message.reply_to_message.from_user:
        target_tg_id = message.reply_to_message.from_user.id
        if len(args) > 1:
            perms = args[1]
    elif len(args) > 1:
        try:
            target_tg_id = int(args[1])
            if len(args) > 2:
                perms = args[2]
        except ValueError:
            pass

    if not target_tg_id:
        await message.answer(
            "Usage: <code>/addstaff &lt;USER_ID&gt; [PERMISSIONS]</code>\n"
            "Example permissions: <code>ban,mute,warn,delete,filters,locks</code>",
            parse_mode="HTML"
        )
        return

    target_user = await user_repo.get_or_create_user(telegram_user_id=target_tg_id)
    actor_db = await user_repo.get_by_telegram_id(message.from_user.id)

    staff = await admin_repo.add_staff(
        group_id=group.id,
        user_id=target_user.id,
        permissions=perms,
        created_by=actor_db.id if actor_db else None
    )

    await perm_service.log_action(
        group=group,
        actor_tg_id=message.from_user.id,
        action="ADD_STAFF",
        target_tg_id=target_tg_id,
        details=f"Permissions: {perms}"
    )

    await message.answer(
        f"✅ <b>Staff Member Added!</b>\n"
        f"• User ID: <code>{target_tg_id}</code>\n"
        f"• Permissions: <code>{perms}</code>",
        parse_mode="HTML"
    )


@staff_router.message(Command("removestaff"))
async def handle_removestaff(message: Message, session: AsyncSession) -> None:
    """Removes a staff member from the group."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    admin_repo = AdminRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_by_telegram_id(message.chat.id)
    if not group:
        return

    actor_role, _ = await perm_service.get_user_role_and_rank(message.chat.id, message.from_user.id, group.id)
    if actor_role < UserRole.ADMIN:
        await message.answer("❌ Only Administrators can remove bot staff.")
        return

    args = message.text.split()
    target_tg_id: Optional[int] = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_tg_id = message.reply_to_message.from_user.id
    elif len(args) > 1:
        try:
            target_tg_id = int(args[1])
        except ValueError:
            pass

    if not target_tg_id:
        await message.answer("Usage: <code>/removestaff &lt;USER_ID&gt;</code> or reply to user.", parse_mode="HTML")
        return

    target_user = await user_repo.get_by_telegram_id(target_tg_id)
    if not target_user:
        await message.answer("User record not found in database.")
        return

    removed = await admin_repo.remove_staff(group.id, target_user.id)
    if removed:
        await perm_service.log_action(
            group=group,
            actor_tg_id=message.from_user.id,
            action="REMOVE_STAFF",
            target_tg_id=target_tg_id
        )
        await message.answer(f"✅ Removed staff privileges for user <code>{target_tg_id}</code>.", parse_mode="HTML")
    else:
        await message.answer(f"User <code>{target_tg_id}</code> is not currently configured as staff.", parse_mode="HTML")


@staff_router.message(Command("staff"))
@staff_router.message(Command("admins"))
async def handle_list_staff(message: Message, session: AsyncSession) -> None:
    """Lists all administrators and configured bot staff."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    user_repo = UserRepository(session)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")

    lines = [f"👑 <b>STAFF & ADMINS — {group.group_name}</b>\n"]

    # 1. Fetch Telegram chat administrators
    try:
        tg_admins = await message.chat.get_administrators()
        lines.append("<b>Telegram Administrators:</b>")
        for adm in tg_admins:
            title = "Owner" if adm.status == "creator" else "Admin"
            u = adm.user
            uname = f" (@{u.username})" if u.username else ""
            lines.append(f"• {u.first_name}{uname} [<code>{u.id}</code>] — <i>{title}</i>")
    except Exception as e:
        logger.debug(f"Failed to fetch tg admins: {e}")

    # 2. Fetch Bot Staff from DB
    bot_staff = await admin_repo.list_staff(group.id)
    if bot_staff:
        lines.append("\n<b>Configured Bot Staff:</b>")
        from database.models.user import User
        for st in bot_staff:
            user = await session.get(User, st.user_id)
            name = user.first_name if user else f"User {st.user_id}"
            lines.append(f"• {name} [<code>{user.telegram_user_id if user else st.user_id}</code>] — Permissions: <code>{st.permissions}</code>")

    await message.answer("\n".join(lines), parse_mode="HTML")
