"""Administrator Dashboard and Settings Handlers."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from bot.filters.admin_filter import IsAdminFilter
from database.repositories.group_repo import GroupRepository
from services.statistics_service import StatisticsService
from bot.keyboards.admin_kb import (
    get_admin_dashboard_keyboard,
    get_deadline_options_keyboard,
    get_required_referrals_keyboard,
    get_failure_action_keyboard
)

admin_router = Router(name="admin_router")
admin_router.message.filter(IsAdminFilter())
admin_router.callback_query.filter(IsAdminFilter())


@admin_router.message(Command("admin"))
@admin_router.message(Command("settings"))
async def handle_admin_command(message: Message, session: AsyncSession) -> None:
    """Opens admin dashboard."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.answer("Please run /admin inside your group to manage its settings.")
        return

    group_repo = GroupRepository(session)
    group = await group_repo.get_or_create_group(
        telegram_group_id=message.chat.id,
        group_name=message.chat.title or "Group"
    )
    settings = await group_repo.get_settings(group.id)

    text = (
        f"⚙️ <b>ADMIN DASHBOARD — {group.group_name}</b>\n\n"
        f"• Referral System: <b>{'ENABLED' if settings.referral_enabled else 'DISABLED'}</b>\n"
        f"• Deadline: <b>{settings.referral_deadline_hours} hours</b>\n"
        f"• Required Referrals: <b>{settings.required_referrals}</b>\n"
        f"• Failure Action: <b>{settings.failure_action}</b>\n"
        f"• Anti-Spam: <b>{'ENABLED' if settings.anti_spam_enabled else 'DISABLED'}</b>\n"
        f"• Warning Limit: <b>{settings.warning_limit}</b>\n\n"
        f"Use the buttons below to configure your group."
    )

    await message.answer(
        text=text,
        reply_markup=get_admin_dashboard_keyboard(group.id, settings),
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data.startswith("adm_tgl_ref:"))
async def toggle_referral(callback: CallbackQuery, session: AsyncSession) -> None:
    group_id = int(callback.data.split(":")[1])
    group_repo = GroupRepository(session)
    settings = await group_repo.get_settings(group_id)
    new_status = not settings.referral_enabled
    await group_repo.update_settings(group_id, referral_enabled=new_status)
    settings = await group_repo.get_settings(group_id)

    await callback.message.edit_reply_markup(
        reply_markup=get_admin_dashboard_keyboard(group_id, settings)
    )
    await callback.answer(f"Referral system is now {'ENABLED' if new_status else 'DISABLED'}")


@admin_router.callback_query(F.data.startswith("adm_tgl_spam:"))
async def toggle_antispam(callback: CallbackQuery, session: AsyncSession) -> None:
    group_id = int(callback.data.split(":")[1])
    group_repo = GroupRepository(session)
    settings = await group_repo.get_settings(group_id)
    new_status = not settings.anti_spam_enabled
    await group_repo.update_settings(group_id, anti_spam_enabled=new_status)
    settings = await group_repo.get_settings(group_id)

    await callback.message.edit_reply_markup(
        reply_markup=get_admin_dashboard_keyboard(group_id, settings)
    )
    await callback.answer(f"Anti-spam is now {'ENABLED' if new_status else 'DISABLED'}")


@admin_router.callback_query(F.data.startswith("adm_menu_deadline:"))
async def menu_deadline(callback: CallbackQuery) -> None:
    group_id = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(
        reply_markup=get_deadline_options_keyboard(group_id)
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_set_dl:"))
async def set_deadline(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    group_id = int(parts[1])
    hours = int(parts[2])
    group_repo = GroupRepository(session)
    await group_repo.update_settings(group_id, referral_deadline_hours=hours)
    settings = await group_repo.get_settings(group_id)

    await callback.message.edit_reply_markup(
        reply_markup=get_admin_dashboard_keyboard(group_id, settings)
    )
    await callback.answer(f"Deadline updated to {hours} hours!")


@admin_router.callback_query(F.data.startswith("adm_menu_req:"))
async def menu_required_referrals(callback: CallbackQuery) -> None:
    group_id = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(
        reply_markup=get_required_referrals_keyboard(group_id)
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_set_req:"))
async def set_required_referrals(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    group_id = int(parts[1])
    count = int(parts[2])
    group_repo = GroupRepository(session)
    await group_repo.update_settings(group_id, required_referrals=count)
    settings = await group_repo.get_settings(group_id)

    await callback.message.edit_reply_markup(
        reply_markup=get_admin_dashboard_keyboard(group_id, settings)
    )
    await callback.answer(f"Required referrals set to {count}!")


@admin_router.callback_query(F.data.startswith("adm_menu_action:"))
async def menu_failure_action(callback: CallbackQuery) -> None:
    group_id = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(
        reply_markup=get_failure_action_keyboard(group_id)
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_set_act:"))
async def set_failure_action(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    group_id = int(parts[1])
    action = parts[2]
    group_repo = GroupRepository(session)
    await group_repo.update_settings(group_id, failure_action=action)
    settings = await group_repo.get_settings(group_id)

    await callback.message.edit_reply_markup(
        reply_markup=get_admin_dashboard_keyboard(group_id, settings)
    )
    await callback.answer(f"Failure action set to {action}!")


@admin_router.callback_query(F.data.startswith("adm_stats:"))
async def admin_view_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    group_id = int(callback.data.split(":")[1])
    from database.models.group import Group
    group = await session.get(Group, group_id)
    if not group:
        await callback.answer("Group not found")
        return

    stats_service = StatisticsService(session, callback.bot)
    text = await stats_service.get_formatted_stats(group)
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_view_rules:"))
async def admin_view_rules(callback: CallbackQuery, session: AsyncSession) -> None:
    group_id = int(callback.data.split(":")[1])
    from database.models.group import Group
    group = await session.get(Group, group_id)
    rules = group.rules if group and group.rules else "No group rules defined yet. Set them using /setrules."
    await callback.message.answer(f"📜 <b>Group Rules:</b>\n\n{rules}", parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_back:"))
async def admin_back(callback: CallbackQuery, session: AsyncSession) -> None:
    group_id = int(callback.data.split(":")[1])
    group_repo = GroupRepository(session)
    settings = await group_repo.get_settings(group_id)
    await callback.message.edit_reply_markup(
        reply_markup=get_admin_dashboard_keyboard(group_id, settings)
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_close:"))
async def admin_close(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer("Closed")
