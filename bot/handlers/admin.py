"""Comprehensive Administrator Dashboard and Settings Handlers."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from bot.filters.admin_filter import IsAdminFilter
from database.repositories.group_repo import GroupRepository
from database.repositories.admin_repo import AdminRepository
from database.repositories.moderation_repo import ModerationRepository
from services.permission_service import PermissionService, UserRole
from services.statistics_service import StatisticsService
from services.activity_service import ActivityService
from bot.keyboards.admin_kb import (
    get_admin_dashboard_keyboard,
    get_referral_settings_keyboard,
    get_deadline_options_keyboard,
    get_required_referrals_keyboard,
    get_failure_action_keyboard,
    get_back_keyboard
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
        f"Select a category below to configure group security, referral rules, moderation, locks, filters, and logs:"
    )

    await message.answer(
        text=text,
        reply_markup=get_admin_dashboard_keyboard(group.id, settings),
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data.startswith("adm_sec:"))
async def handle_admin_section(callback: CallbackQuery, session: AsyncSession) -> None:
    """Handles sub-menu category navigations."""
    parts = callback.data.split(":")
    section = parts[1]
    group_id = int(parts[2])

    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    settings = await group_repo.get_settings(group_id)

    if section == "ref":
        text = (
            f"🎯 <b>REFERRAL SETTINGS</b>\n\n"
            f"• Referral System: <b>{'ENABLED' if settings.referral_enabled else 'DISABLED'}</b>\n"
            f"• Deadline: <b>{settings.referral_deadline_hours} hours</b>\n"
            f"• Required Referrals: <b>{settings.required_referrals}</b>\n"
            f"• Failure Action: <b>{settings.failure_action}</b>"
        )
        await callback.message.edit_text(text, reply_markup=get_referral_settings_keyboard(group_id, settings), parse_mode="HTML")

    elif section == "mod":
        text = (
            "🔨 <b>MODERATION COMMANDS</b>\n\n"
            "• <code>/ban &lt;user&gt; [duration] [reason]</code>\n"
            "• <code>/unban &lt;user&gt;</code>\n"
            "• <code>/banlist</code>\n"
            "• <code>/mute &lt;user&gt; [duration] [reason]</code>\n"
            "• <code>/unmute &lt;user&gt;</code>\n"
            "• <code>/mutelist</code>\n"
            "• <code>/warn &lt;user&gt; [reason]</code>\n"
            "• <code>/warnings &lt;user&gt;</code>\n"
            "• <code>/resetwarnings &lt;user&gt;</code>\n"
            "• <code>/history &lt;user&gt;</code>"
        )
        await callback.message.edit_text(text, reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    elif section == "staff":
        staff_list = await admin_repo.list_staff(group_id)
        text = (
            f"👑 <b>STAFF MANAGEMENT</b>\n\n"
            f"• Configured Bot Staff: <b>{len(staff_list)}</b>\n\n"
            f"Commands:\n"
            f"• <code>/addstaff &lt;user_id&gt; [permissions]</code>\n"
            f"• <code>/removestaff &lt;user_id&gt;</code>\n"
            f"• <code>/staff</code> to view all"
        )
        await callback.message.edit_text(text, reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    elif section == "members":
        text = (
            "👥 <b>MEMBER MANAGEMENT</b>\n\n"
            "Commands:\n"
            "• <code>/userinfo &lt;user&gt;</code> — Detailed member profile\n"
            "• <code>/inactive [days]</code> — Find inactive members\n"
            "• <code>/exempt &lt;user&gt;</code> — Exempt from referral deadline\n"
            "• <code>/reset_timer &lt;user&gt; [hours]</code> — Reset deadline"
        )
        await callback.message.edit_text(text, reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    elif section == "locks":
        locks = await admin_repo.get_or_create_locks(group_id)
        text = (
            "🔒 <b>CONTENT LOCKS</b>\n\n"
            f"• All: <b>{locks.lock_all}</b>\n"
            f"• Text: <b>{locks.lock_text}</b> | Photos: <b>{locks.lock_photos}</b>\n"
            f"• Videos: <b>{locks.lock_videos}</b> | Stickers: <b>{locks.lock_stickers}</b>\n"
            f"• Links: <b>{locks.lock_links}</b> | Voice: <b>{locks.lock_voice}</b>\n\n"
            "Use <code>/lock &lt;type&gt;</code> and <code>/unlock &lt;type&gt;</code> to change."
        )
        await callback.message.edit_text(text, reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    elif section == "words":
        words = await admin_repo.list_banned_words(group_id)
        text = (
            f"🚫 <b>BANNED WORDS FILTER</b>\n\n"
            f"• Total Banned Words: <b>{len(words)}</b>\n\n"
            f"Commands:\n"
            f"• <code>/addword &lt;word&gt; [substring]</code>\n"
            f"• <code>/delword &lt;word&gt;</code>\n"
            f"• <code>/badwords</code>\n"
            f"• <code>/clearwords</code>"
        )
        await callback.message.edit_text(text, reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    elif section == "links":
        domains = await admin_repo.list_domains(group_id)
        text = (
            f"🔗 <b>LINK FILTER SETTINGS</b>\n\n"
            f"• Mode: <b>{settings.link_filter_mode}</b>\n"
            f"• Domain Rules: <b>{len(domains)}</b>\n\n"
            f"Commands:\n"
            f"• <code>/setlinkmode ALLOW_ALL | BLOCK_ALL | TELEGRAM_ONLY</code>\n"
            f"• <code>/allowlink &lt;domain&gt;</code>\n"
            f"• <code>/blocklink &lt;domain&gt;</code>\n"
            f"• <code>/links</code>"
        )
        await callback.message.edit_text(text, reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    elif section == "spam":
        text = (
            f"🛡 <b>ANTI-SPAM & FLOOD PROTECTION</b>\n\n"
            f"• Anti-Spam: <b>{'ENABLED' if settings.anti_spam_enabled else 'DISABLED'}</b>\n"
            f"• Warning Limit: <b>{settings.warning_limit}</b>\n"
            f"• Flood Limit: <b>{settings.flood_limit_messages} msgs in {settings.flood_limit_seconds}s</b>"
        )
        await callback.message.edit_text(text, reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    elif section == "raid":
        text = (
            f"🚨 <b>ANTI-RAID SYSTEM</b>\n\n"
            f"• Raid Mode: <b>{'ACTIVATED' if settings.raid_mode else 'DEACTIVATED'}</b>\n\n"
            f"Commands:\n"
            f"• <code>/raidmode on</code>\n"
            f"• <code>/raidmode off</code>"
        )
        await callback.message.edit_text(text, reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    elif section == "captcha":
        text = (
            f"🤖 <b>CAPTCHA NEW MEMBER VERIFICATION</b>\n\n"
            f"• Status: <b>{'ENABLED' if settings.captcha_enabled else 'DISABLED'}</b>\n\n"
            f"Click button below to toggle."
        )
        tgl_kb = [
            [callback.message.reply_markup.inline_keyboard[0][0]] if callback.message.reply_markup else [],
            [{"text": "🔙 Back", "callback_data": f"adm_back:{group_id}"}]
        ]
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Toggle Captcha ON/OFF", callback_data=f"adm_tgl_cpt:{group_id}")],
                [InlineKeyboardButton(text="🔙 Back", callback_data=f"adm_back:{group_id}")]
            ]
        )
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    elif section == "welc":
        text = (
            f"👋 <b>WELCOME & GOODBYE</b>\n\n"
            f"• Welcome Enabled: <b>{settings.welcome_enabled}</b>\n"
            f"• Goodbye Enabled: <b>{settings.goodbye_enabled}</b>\n\n"
            f"Commands:\n"
            f"• <code>/welcome</code>\n"
            f"• <code>/setwelcome &lt;msg&gt;</code>\n"
            f"• <code>/goodbye</code>\n"
            f"• <code>/setgoodbye &lt;msg&gt;</code>\n"
            f"• <code>/togglegoodbye</code>"
        )
        await callback.message.edit_text(text, reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    elif section == "autodel":
        text = (
            f"🗑 <b>AUTO-DELETE</b>\n\n"
            f"• Delay: <b>{settings.auto_delete_seconds}s</b>\n\n"
            f"Commands:\n"
            f"• <code>/autodelete &lt;seconds&gt;</code>\n"
            f"• <code>/autodelete off</code>\n"
            f"• <code>/del</code>\n"
            f"• <code>/purge [count]</code>\n"
            f"• <code>/delall</code>"
        )
        await callback.message.edit_text(text, reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    elif section == "stats":
        from database.models.group import Group
        group = await session.get(Group, group_id)
        if group:
            stats_service = StatisticsService(session, callback.bot)
            st_text = await stats_service.get_formatted_stats(group)
            await callback.message.edit_text(st_text, reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    elif section == "top":
        act_service = ActivityService(session, callback.bot)
        top_text = await act_service.get_top_chatters_text(group_id)
        await callback.message.edit_text(top_text, reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    elif section == "logs":
        mod_repo = ModerationRepository(session)
        logs = await mod_repo.get_recent_logs(group_id, limit=8)
        lines = ["📋 <b>RECENT MODERATION LOGS</b>\n"]
        if not logs:
            lines.append("<i>No recent moderation logs found.</i>")
        else:
            for l in logs:
                dt = l.created_at.strftime("%m-%d %H:%M")
                lines.append(f"• [<b>{l.action}</b>] {dt} — <i>{l.details or ''}</i>")
        await callback.message.edit_text("\n".join(lines), reply_markup=get_back_keyboard(group_id), parse_mode="HTML")

    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_tgl_cpt:"))
async def toggle_captcha(callback: CallbackQuery, session: AsyncSession) -> None:
    group_id = int(callback.data.split(":")[1])
    group_repo = GroupRepository(session)
    settings = await group_repo.get_settings(group_id)
    new_val = not settings.captcha_enabled
    await group_repo.update_settings(group_id, captcha_enabled=new_val)
    await callback.answer(f"Captcha verification is now {'ENABLED' if new_val else 'DISABLED'}")
    # Return to captcha menu
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Toggle Captcha ON/OFF", callback_data=f"adm_tgl_cpt:{group_id}")],
            [InlineKeyboardButton(text="🔙 Back", callback_data=f"adm_back:{group_id}")]
        ]
    )
    text = (
        f"🤖 <b>CAPTCHA NEW MEMBER VERIFICATION</b>\n\n"
        f"• Status: <b>{'ENABLED' if new_val else 'DISABLED'}</b>\n\n"
        f"Click button below to toggle."
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("adm_tgl_ref:"))
async def toggle_referral(callback: CallbackQuery, session: AsyncSession) -> None:
    group_id = int(callback.data.split(":")[1])
    group_repo = GroupRepository(session)
    settings = await group_repo.get_settings(group_id)
    new_status = not settings.referral_enabled
    await group_repo.update_settings(group_id, referral_enabled=new_status)
    settings = await group_repo.get_settings(group_id)

    text = (
        f"🎯 <b>REFERRAL SETTINGS</b>\n\n"
        f"• Referral System: <b>{'ENABLED' if settings.referral_enabled else 'DISABLED'}</b>\n"
        f"• Deadline: <b>{settings.referral_deadline_hours} hours</b>\n"
        f"• Required Referrals: <b>{settings.required_referrals}</b>\n"
        f"• Failure Action: <b>{settings.failure_action}</b>"
    )
    await callback.message.edit_text(text, reply_markup=get_referral_settings_keyboard(group_id, settings), parse_mode="HTML")
    await callback.answer(f"Referral system is now {'ENABLED' if new_status else 'DISABLED'}")


@admin_router.callback_query(F.data.startswith("adm_menu_deadline:"))
async def menu_deadline(callback: CallbackQuery) -> None:
    group_id = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=get_deadline_options_keyboard(group_id))
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_set_dl:"))
async def set_deadline(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    group_id = int(parts[1])
    hours = int(parts[2])
    group_repo = GroupRepository(session)
    await group_repo.update_settings(group_id, referral_deadline_hours=hours)
    settings = await group_repo.get_settings(group_id)

    text = (
        f"🎯 <b>REFERRAL SETTINGS</b>\n\n"
        f"• Referral System: <b>{'ENABLED' if settings.referral_enabled else 'DISABLED'}</b>\n"
        f"• Deadline: <b>{settings.referral_deadline_hours} hours</b>\n"
        f"• Required Referrals: <b>{settings.required_referrals}</b>\n"
        f"• Failure Action: <b>{settings.failure_action}</b>"
    )
    await callback.message.edit_text(text, reply_markup=get_referral_settings_keyboard(group_id, settings), parse_mode="HTML")
    await callback.answer(f"Deadline updated to {hours} hours!")


@admin_router.callback_query(F.data.startswith("adm_menu_req:"))
async def menu_required_referrals(callback: CallbackQuery) -> None:
    group_id = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=get_required_referrals_keyboard(group_id))
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_set_req:"))
async def set_required_referrals(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    group_id = int(parts[1])
    count = int(parts[2])
    group_repo = GroupRepository(session)
    await group_repo.update_settings(group_id, required_referrals=count)
    settings = await group_repo.get_settings(group_id)

    text = (
        f"🎯 <b>REFERRAL SETTINGS</b>\n\n"
        f"• Referral System: <b>{'ENABLED' if settings.referral_enabled else 'DISABLED'}</b>\n"
        f"• Deadline: <b>{settings.referral_deadline_hours} hours</b>\n"
        f"• Required Referrals: <b>{settings.required_referrals}</b>\n"
        f"• Failure Action: <b>{settings.failure_action}</b>"
    )
    await callback.message.edit_text(text, reply_markup=get_referral_settings_keyboard(group_id, settings), parse_mode="HTML")
    await callback.answer(f"Required referrals set to {count}!")


@admin_router.callback_query(F.data.startswith("adm_menu_action:"))
async def menu_failure_action(callback: CallbackQuery) -> None:
    group_id = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=get_failure_action_keyboard(group_id))
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_set_act:"))
async def set_failure_action(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    group_id = int(parts[1])
    action = parts[2]
    group_repo = GroupRepository(session)
    await group_repo.update_settings(group_id, failure_action=action)
    settings = await group_repo.get_settings(group_id)

    text = (
        f"🎯 <b>REFERRAL SETTINGS</b>\n\n"
        f"• Referral System: <b>{'ENABLED' if settings.referral_enabled else 'DISABLED'}</b>\n"
        f"• Deadline: <b>{settings.referral_deadline_hours} hours</b>\n"
        f"• Required Referrals: <b>{settings.required_referrals}</b>\n"
        f"• Failure Action: <b>{settings.failure_action}</b>"
    )
    await callback.message.edit_text(text, reply_markup=get_referral_settings_keyboard(group_id, settings), parse_mode="HTML")
    await callback.answer(f"Failure action set to {action}!")


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
    from database.models.group import Group
    group = await session.get(Group, group_id)
    settings = await group_repo.get_settings(group_id)
    text = (
        f"⚙️ <b>ADMIN DASHBOARD — {group.group_name if group else 'Group'}</b>\n\n"
        f"Select a category below to configure group security, referral rules, moderation, locks, filters, and logs:"
    )
    await callback.message.edit_text(
        text=text,
        reply_markup=get_admin_dashboard_keyboard(group_id, settings),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_close:"))
async def admin_close(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer("Closed")
