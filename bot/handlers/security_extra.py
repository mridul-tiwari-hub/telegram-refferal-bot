"""Anti-Raid and Captcha Callback Handlers."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.group_repo import GroupRepository
from database.repositories.user_repo import UserRepository
from database.models.group import Group
from database.models.user import User
from services.permission_service import PermissionService
from services.captcha_service import CaptchaService
from utils.logging import get_logger

logger = get_logger(__name__)
security_extra_router = Router(name="security_extra_router")


@security_extra_router.message(Command("raidmode"))
async def handle_raidmode(message: Message, session: AsyncSession) -> None:
    """Manually enables or disables raid mode."""
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
    if len(tokens) < 2 or tokens[1].lower() not in ["on", "off"]:
        settings = await group_repo.get_settings(group.id)
        current = "ON" if settings.raid_mode else "OFF"
        await message.answer(f"Raid mode is currently <b>{current}</b>.\nUsage: <code>/raidmode &lt;on|off&gt;</code>", parse_mode="HTML")
        return

    enable = tokens[1].lower() == "on"
    await group_repo.update_settings(group.id, raid_mode=enable)
    await perm_service.log_action(
        group=group,
        actor_tg_id=message.from_user.id,
        action="RAID_MODE_TOGGLE",
        details=f"Enabled: {enable}"
    )

    status_text = "ACTIVATED 🚨. New members will be restricted automatically." if enable else "DEACTIVATED 🛡. Normal join policy restored."
    await message.answer(f"✅ Raid mode has been {status_text}", parse_mode="HTML")


@security_extra_router.callback_query(F.data.startswith("cpt_vfy:"))
async def handle_captcha_verify(callback: CallbackQuery, session: AsyncSession) -> None:
    """Handles verification button click by new member."""
    parts = callback.data.split(":")
    group_id = int(parts[1])
    target_user_id = int(parts[2])

    user_repo = UserRepository(session)
    caller_db = await user_repo.get_by_telegram_id(callback.from_user.id)

    # Re-verify that caller is the target user
    if not caller_db or caller_db.id != target_user_id:
        await callback.answer("❌ This verification button is not for you.", show_alert=True)
        return

    group = await session.get(Group, group_id)
    target_user = await session.get(User, target_user_id)

    if not group or not target_user:
        await callback.answer("Record not found.", show_alert=True)
        return

    captcha_service = CaptchaService(session, callback.bot)
    verified = await captcha_service.verify_member(group, target_user)

    if verified:
        await callback.answer("✅ Verification successful! Welcome to the group.", show_alert=True)
    else:
        await callback.answer("Verification expired or already completed.", show_alert=True)
