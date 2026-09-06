import html
from typing import Optional
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.group_repo import GroupRepository
from database.repositories.user_repo import UserRepository
from database.repositories.admin_repo import AdminRepository
from services.statistics_service import StatisticsService
from services.referral_service import ReferralService
from services.member_service import MemberService
from services.invite_link_service import InviteLinkService
from services.permission_service import PermissionService, UserRole
from bot.keyboards.user_kb import get_tree_pagination_keyboard
from bot.filters.admin_filter import IsAdminFilter

commands_router = Router(name="commands_router")


@commands_router.message(Command("rules"))
async def handle_rules(message: Message, session: AsyncSession) -> None:
    """Displays current group rules."""
    group_repo = GroupRepository(session)
    group = await group_repo.get_by_telegram_id(message.chat.id)
    if not group or not group.rules:
        await message.answer("📜 <i>No group rules have been set yet.</i>", parse_mode="HTML")
        return
    await message.answer(f"📜 <b>GROUP RULES</b>\n\n{group.rules}", parse_mode="HTML")


@commands_router.message(Command("setrules"), IsAdminFilter())
async def handle_setrules(message: Message, session: AsyncSession) -> None:
    """Sets or updates group rules."""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: <code>/setrules <rules text></code>", parse_mode="HTML")
        return

    new_rules = args[1]
    group_repo = GroupRepository(session)
    group = await group_repo.get_or_create_group(
        telegram_group_id=message.chat.id,
        group_name=message.chat.title or "Group"
    )
    await group_repo.set_rules(group.id, new_rules)
    await message.answer("✅ Group rules have been successfully updated!", parse_mode="HTML")


@commands_router.message(Command("stats"))
async def handle_stats(message: Message, session: AsyncSession) -> None:
    """Displays group stats and referral leaderboard."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.answer("Please use /stats inside a group.")
        return

    group_repo = GroupRepository(session)
    group = await group_repo.get_or_create_group(
        telegram_group_id=message.chat.id,
        group_name=message.chat.title or "Group"
    )
    stats_service = StatisticsService(session, message.bot)
    text = await stats_service.get_formatted_stats(group)
    await message.answer(text, parse_mode="HTML")


@commands_router.message(Command("referrals"))
async def handle_referrals(message: Message, session: AsyncSession) -> None:
    """Displays recursive referral tree with pagination."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.answer("Please use /referrals inside a group.")
        return

    group_repo = GroupRepository(session)
    group = await group_repo.get_or_create_group(
        telegram_group_id=message.chat.id,
        group_name=message.chat.title or "Group"
    )
    ref_service = ReferralService(session, message.bot)
    text, current_page, total_pages = await ref_service.generate_referral_tree_text(
        group_id=group.id,
        page=1
    )
    markup = get_tree_pagination_keyboard(group.id, current_page, total_pages)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


@commands_router.message(Command("userinfo"))
@commands_router.message(Command("profile"))
@commands_router.message(Command("me"))
@commands_router.message(Command("myinfo"))
@commands_router.message(Command("whois"))
@commands_router.message(Command("member"))
async def handle_userinfo(message: Message, session: AsyncSession) -> None:
    """Inspects detailed profile and role of a member or oneself."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.answer("Please use this command inside a group.")
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    admin_repo = AdminRepository(session)
    member_service = MemberService(session, message.bot)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(
        telegram_group_id=message.chat.id,
        group_name=message.chat.title or "Group"
    )

    args = message.text.split()[1:]
    target_tg_id: Optional[int] = None
    target_user: Optional[User] = None

    if message.reply_to_message:
        if message.reply_to_message.from_user:
            replied = message.reply_to_message.from_user
            if replied.is_bot:
                await message.answer("ℹ️ Cannot view userinfo for bots. Please reply to a regular group member or provide their user ID.", parse_mode="HTML")
                return
            target_tg_id = replied.id
            target_user = await user_repo.get_or_create_user(
                telegram_user_id=replied.id,
                username=replied.username,
                first_name=replied.first_name or "",
                last_name=replied.last_name
            )
        else:
            await message.answer("ℹ️ Cannot resolve user from that message (sent by an anonymous sender or channel).", parse_mode="HTML")
            return
    elif args:
        first = args[0].strip()
        if first.startswith("@"):
            username = first.lstrip("@")
            found_user = await user_repo.get_by_username(username)
            if found_user:
                target_tg_id = found_user.telegram_user_id
                target_user = found_user
            else:
                await message.answer(f"❌ User @{html.escape(username)} not found in database. They must send a message or interact in the group first.")
                return
        else:
            try:
                target_tg_id = int(first)
            except ValueError:
                await message.answer("Usage: <code>/userinfo [@username | USER_ID]</code> or reply to a message, or simply <code>/userinfo</code> for your own profile.", parse_mode="HTML")
                return
    else:
        # Defaults to caller inspecting their own profile
        caller = message.from_user
        if not caller:
            await message.answer("Could not identify sender.")
            return
        target_tg_id = caller.id
        target_user = await user_repo.get_or_create_user(
            telegram_user_id=caller.id,
            username=caller.username,
            first_name=caller.first_name or "",
            last_name=caller.last_name
        )

    # If numeric ID was passed and target_user is not yet resolved:
    if not target_user and target_tg_id:
        target_user = await user_repo.get_by_telegram_id(target_tg_id)
        if not target_user:
            try:
                chat_member = await message.chat.get_member(target_tg_id)
                if chat_member and chat_member.user:
                    u = chat_member.user
                    target_user = await user_repo.get_or_create_user(
                        telegram_user_id=u.id,
                        username=u.username,
                        first_name=u.first_name or "",
                        last_name=u.last_name
                    )
            except Exception:
                pass

    if not target_user:
        await message.answer("User record could not be found. Ensure the user is a member of this chat.")
        return

    # Permission check: Only Owner, Admins, or Staff can inspect other members
    caller_id = message.from_user.id if message.from_user else 0
    is_self = (target_tg_id == caller_id)
    is_anon_admin = (
        (message.sender_chat and message.sender_chat.id == message.chat.id) or
        (caller_id == 1087968824)
    )

    if not is_self and not is_anon_admin:
        caller_role, caller_role_name = await perm_service.get_user_role_and_rank(
            chat_id=message.chat.id,
            user_id=caller_id,
            group_db_id=group.id
        )
        if caller_role < UserRole.STAFF:
            await message.answer(
                "❌ <b>Access Denied</b>: Only Administrators and Owners can view other members' information.\n"
                "You can view your own profile by sending <code>/userinfo</code> without replying or arguments.",
                parse_mode="HTML"
            )
            return

    # Determine user role and rank in this group
    role_enum, role_name = await perm_service.get_user_role_and_rank(
        chat_id=message.chat.id,
        user_id=target_tg_id,
        group_db_id=group.id
    )

    role_icons = {
        UserRole.OWNER: "👑 Owner",
        UserRole.ADMIN: "🛡️ Administrator",
        UserRole.STAFF: "⭐ Staff (Bot Moderator)",
        UserRole.MEMBER: "👤 Member",
        UserRole.RESTRICTED: "⛔ Restricted Member",
        UserRole.BANNED: "🔨 Banned Member"
    }
    role_display = role_icons.get(role_enum, f"👤 {role_name}")

    staff_info = ""
    if role_enum == UserRole.STAFF:
        staff_rec = await admin_repo.get_staff(group.id, target_user.id)
        if staff_rec:
            staff_info = f"\n• Staff Permissions: <code>{html.escape(staff_rec.permissions)}</code>"

    profile = await member_service.get_member_profile(target_user.id, group.id)
    if not profile:
        await message.answer("Could not load user profile.")
        return

    req = profile["requirement"]
    referrer = profile["referrer"]
    ref_name = f"@{referrer.username}" if referrer and referrer.username else (referrer.first_name if referrer else "None")

    inv_link = profile["invite_link"]
    if inv_link and inv_link.startswith("http"):
        link_display = f'<a href="{html.escape(inv_link)}">{html.escape(inv_link)}</a>'
    else:
        link_display = html.escape(str(inv_link or "None"))

    full_name = html.escape(f"{target_user.first_name} {target_user.last_name or ''}".strip())
    safe_username = html.escape(f"@{target_user.username}") if target_user.username else "@None"
    safe_ref = html.escape(str(ref_name))

    text = (
        f"👤 <b>USER INFORMATION</b>\n\n"
        f"• Name: <b>{full_name}</b>\n"
        f"• Telegram ID: <code>{target_user.telegram_user_id}</code>\n"
        f"• Username: {safe_username}\n"
        f"• Role: <b>{role_display}</b>{staff_info}\n"
        f"• Referred By: <b>{safe_ref}</b>\n"
        f"• Direct Referrals: <b>{profile['referrals_count']}</b>\n"
        f"• Warnings: <b>{profile['warnings_count']}</b>\n"
        f"• Requirement Status: <b>{req.status if req else 'N/A'}</b>\n"
        f"• Progress: <b>{req.completed_referrals if req else 0}/{req.required_referrals if req else 0}</b>\n"
        f"• Exempt: <b>{req.is_exempt if req else False}</b>\n"
        f"• Time Remaining: <b>{profile['time_remaining']}</b>\n"
        f"• Active Link: {link_display}"
    )
    try:
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send HTML userinfo: {e}")
        plain = text.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "")
        await message.answer(plain)


@commands_router.message(Command("exempt"), IsAdminFilter())
async def handle_exempt(message: Message, session: AsyncSession) -> None:
    """Toggles exemption for a user."""
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
        await message.answer("Usage: <code>/exempt &lt;USER_ID&gt;</code> or reply to user.", parse_mode="HTML")
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    member_service = MemberService(session, message.bot)

    group = await group_repo.get_by_telegram_id(message.chat.id)
    user = await user_repo.get_by_telegram_id(target_tg_id)
    admin = await user_repo.get_by_telegram_id(message.from_user.id)

    if not group or not user:
        await message.answer("User or group record not found.")
        return

    req = await member_service.exempt_member(
        user=user,
        group=group,
        is_exempt=True,
        admin_id=admin.id if admin else None
    )
    await message.answer(f"🛡 User <code>{user.telegram_user_id}</code> is now <b>EXEMPT</b> from referral requirements.", parse_mode="HTML")


@commands_router.message(Command("reset_timer"), IsAdminFilter())
async def handle_reset_timer(message: Message, session: AsyncSession) -> None:
    """Resets the referral deadline timer for a user."""
    args = message.text.split()[1:]
    target_tg_id: Optional[int] = None
    hours = 24

    if message.reply_to_message and message.reply_to_message.from_user:
        target_tg_id = message.reply_to_message.from_user.id
        if args:
            try:
                hours = int(args[0])
            except ValueError:
                pass
    elif args:
        try:
            target_tg_id = int(args[0])
            if len(args) > 1:
                hours = int(args[1])
        except ValueError:
            pass

    if not target_tg_id:
        await message.answer("Usage: <code>/reset_timer &lt;USER_ID&gt; [HOURS]</code>", parse_mode="HTML")
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    member_service = MemberService(session, message.bot)

    group = await group_repo.get_by_telegram_id(message.chat.id)
    user = await user_repo.get_by_telegram_id(target_tg_id)
    admin = await user_repo.get_by_telegram_id(message.from_user.id)

    if not group or not user:
        await message.answer("User or group not found.")
        return

    await member_service.reset_member_timer(user, group, hours, admin.id if admin else None)
    await message.answer(f"⏳ Referral timer for user <code>{user.telegram_user_id}</code> has been reset to <b>{hours} hours</b>.", parse_mode="HTML")


@commands_router.message(Command("regenerate_link"), IsAdminFilter())
async def handle_regenerate_link(message: Message, session: AsyncSession) -> None:
    """Regenerates a member's invite link."""
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
        await message.answer("Usage: <code>/regenerate_link &lt;USER_ID&gt;</code>", parse_mode="HTML")
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    invite_service = InviteLinkService(session, message.bot)

    group = await group_repo.get_by_telegram_id(message.chat.id)
    user = await user_repo.get_by_telegram_id(target_tg_id)

    if not group or not user:
        await message.answer("User or group not found.")
        return

    new_link = await invite_service.revoke_and_regenerate(user, group)
    if new_link:
        await message.answer(f"✅ New link generated for <code>{user.telegram_user_id}</code>:\n<code>{new_link.telegram_invite_link}</code>", parse_mode="HTML")
    else:
        await message.answer("Failed to regenerate Telegram invite link.")
