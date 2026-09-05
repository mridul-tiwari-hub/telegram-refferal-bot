"""User Referral Dashboard and Status Handlers."""
from typing import Optional, Tuple
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.user_repo import UserRepository
from database.repositories.group_repo import GroupRepository
from database.repositories.referral_repo import ReferralRepository
from database.models.referral_requirement import ReferralRequirement
from services.invite_link_service import InviteLinkService
from services.referral_service import ReferralService
from bot.keyboards.user_kb import get_status_keyboard, get_tree_pagination_keyboard
from utils.security import format_time_remaining

referral_router = Router(name="referral_router")


def get_status_and_timer_display(req: Optional[ReferralRequirement]) -> Tuple[str, str, str]:
    """Returns (status_str, progress_str, time_remaining_str)."""
    if not req:
        return "ACTIVE", "0 / 1", "No active deadline"

    progress_str = f"{req.completed_referrals} / {req.required_referrals}"

    if req.status == "COMPLETED" or req.completed_referrals >= req.required_referrals:
        status_str = "COMPLETED ✅"
        time_remaining_str = "🎉 Completed! (Timer stopped — you are safe)"
    elif req.status == "EXEMPT" or req.is_exempt:
        status_str = "EXEMPT 🛡"
        time_remaining_str = "🛡 Exempt (No timer)"
    elif req.status == "FAILED":
        status_str = "FAILED ❌"
        time_remaining_str = "❌ Expired"
    else:
        status_str = "PENDING ⏳"
        time_remaining_str, _ = format_time_remaining(req.deadline)

    return status_str, progress_str, time_remaining_str


@referral_router.message(CommandStart())
async def handle_start(message: Message, session: AsyncSession) -> None:
    """
    Handles /start in private chat.
    If called with ref payload (e.g. /start ref_123), associates or displays status for that group.
    """
    user_repo = UserRepository(session)
    group_repo = GroupRepository(session)
    referral_repo = ReferralRepository(session)
    invite_service = InviteLinkService(session, message.bot)

    # Register/update user
    user = await user_repo.get_or_create_user(
        telegram_user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    args = message.text.split()[1:] if message.text else []
    target_group_id: Optional[int] = None
    if args and args[0].startswith("ref_"):
        try:
            target_group_id = int(args[0].replace("ref_", ""))
        except ValueError:
            target_group_id = None

    # If no specific target group passed, find user's most recent requirement
    if not target_group_id:
        # Check if user has active requirements
        from sqlalchemy import select, desc
        from database.models.referral_requirement import ReferralRequirement
        stmt = (
            select(ReferralRequirement)
            .where(ReferralRequirement.user_id == user.id)
            .order_by(desc(ReferralRequirement.id))
        )
        res = await session.execute(stmt)
        latest_req = res.scalars().first()
        if latest_req:
            target_group_id = latest_req.group_id

    if not target_group_id:
        await message.answer(
            "🎉 <b>Welcome to the Referral Growth System!</b>\n\n"
            "You don't currently belong to an active group with referral requirements.\n"
            "Join one of our partner groups and click the referral button to start sharing!",
            parse_mode="HTML"
        )
        return

    from database.models.group import Group
    group = await session.get(Group, target_group_id)
    if not group:
        await message.answer("Group not found or is no longer active.")
        return

    # Ensure invite link exists
    link = await invite_service.get_or_create_referral_link(user, group)
    req = await referral_repo.get_requirement(user.id, group.id)

    # If requirement doesn't exist yet, auto-create it with group settings
    settings = await group_repo.get_settings(group.id)
    if not req and settings.referral_enabled:
        from datetime import datetime, timedelta, timezone
        deadline = datetime.now(timezone.utc) + timedelta(hours=settings.referral_deadline_hours)
        req = await referral_repo.create_requirement(
            user_id=user.id,
            group_id=group.id,
            deadline=deadline,
            required_referrals=settings.required_referrals
        )

    status_str, progress_str, time_remaining_str = get_status_and_timer_display(req)

    invite_url = link.telegram_invite_link if link else "Could not generate link"
    link_display = f'<a href="{invite_url}">{invite_url}</a>' if invite_url.startswith("http") else invite_url

    text = (
        f"🎉 <b>Welcome!</b>\n\n"
        f"Welcome to the Referral Growth System for <b>{group.group_name}</b>.\n\n"
        f"🔗 <b>Your Personal Referral Link:</b>\n"
        f"{link_display}\n\n"
        f"📊 <b>Your Progress:</b>\n"
        f"Successful Referrals: <b>{progress_str}</b>\n"
        f"Status: <b>{status_str}</b>\n\n"
        f"⏳ <b>Time Remaining:</b>\n"
        f"<b>{time_remaining_str}</b>\n\n"
        f"Share your personal link and successfully invite the required number of new members before your deadline."
    )

    await message.answer(
        text,
        reply_markup=get_status_keyboard(group.id, invite_url=link.telegram_invite_link if link else None),
        parse_mode="HTML"
    )


@referral_router.message(Command("status"))
async def handle_status(message: Message, session: AsyncSession) -> None:
    """Displays dynamic referral status and time remaining."""
    user_repo = UserRepository(session)
    group_repo = GroupRepository(session)
    referral_repo = ReferralRepository(session)
    invite_service = InviteLinkService(session, message.bot)

    user = await user_repo.get_or_create_user(
        telegram_user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    # If in group, use current group; if in private, find group
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        group = await group_repo.get_or_create_group(
            telegram_group_id=message.chat.id,
            group_name=message.chat.title or "Group"
        )
    else:
        from sqlalchemy import select, desc
        from database.models.referral_requirement import ReferralRequirement
        stmt = (
            select(ReferralRequirement)
            .where(ReferralRequirement.user_id == user.id)
            .order_by(desc(ReferralRequirement.id))
        )
        res = await session.execute(stmt)
        latest_req = res.scalars().first()
        group = await session.get(group_repo.session.get_bind().dialect.name and group_repo.get_by_telegram_id(latest_req.group_id) if False else None) if False else None
        if latest_req:
            from database.models.group import Group
            group = await session.get(Group, latest_req.group_id)
        else:
            group = None

    if not group:
        await message.answer(
            "You don't have an active referral requirement in this chat.",
            parse_mode="HTML"
        )
        return

    link = await invite_service.get_or_create_referral_link(user, group)
    req = await referral_repo.get_requirement(user.id, group.id)

    # Auto-create requirement if missing and referral is enabled
    settings = await group_repo.get_settings(group.id)
    if not req and settings.referral_enabled:
        from datetime import datetime, timedelta, timezone
        deadline = datetime.now(timezone.utc) + timedelta(hours=settings.referral_deadline_hours)
        req = await referral_repo.create_requirement(
            user_id=user.id,
            group_id=group.id,
            deadline=deadline,
            required_referrals=settings.required_referrals
        )

    status_str, progress_str, time_remaining_str = get_status_and_timer_display(req)

    invite_url = link.telegram_invite_link if link else "Could not generate link"
    link_display = f'<a href="{invite_url}">{invite_url}</a>' if invite_url.startswith("http") else invite_url

    text = (
        f"📊 <b>Referral Status</b>\n\n"
        f"🔗 <b>Your Personal Invite Link:</b>\n"
        f"{link_display}\n\n"
        f"👥 <b>Successful Referrals:</b>\n"
        f"<b>{progress_str}</b>\n\n"
        f"📌 <b>Status:</b>\n"
        f"<b>{status_str}</b>\n\n"
        f"⏳ <b>Time Remaining:</b>\n"
        f"<b>{time_remaining_str}</b>"
    )

    await message.answer(
        text,
        reply_markup=get_status_keyboard(group.id, invite_url=link.telegram_invite_link if link else None),
        parse_mode="HTML"
    )


@referral_router.callback_query(F.data.startswith("user_refresh_status:"))
async def handle_refresh_status_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Refreshes status message with recalculated dynamic time."""
    group_id = int(callback.data.split(":")[1])
    user_repo = UserRepository(session)
    group_repo = GroupRepository(session)
    referral_repo = ReferralRepository(session)
    invite_service = InviteLinkService(session, callback.bot)

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("User record not found", show_alert=True)
        return

    from database.models.group import Group
    group = await session.get(Group, group_id)
    if not group:
        await callback.answer("Group not found", show_alert=True)
        return

    link = await invite_service.get_or_create_referral_link(user, group)
    req = await referral_repo.get_requirement(user.id, group.id)

    # Auto-create requirement if missing and referral is enabled
    settings = await group_repo.get_settings(group.id)
    if not req and settings.referral_enabled:
        from datetime import datetime, timedelta, timezone
        deadline = datetime.now(timezone.utc) + timedelta(hours=settings.referral_deadline_hours)
        req = await referral_repo.create_requirement(
            user_id=user.id,
            group_id=group.id,
            deadline=deadline,
            required_referrals=settings.required_referrals
        )

    status_str, progress_str, time_remaining_str = get_status_and_timer_display(req)

    invite_url = link.telegram_invite_link if link else "Could not generate link"
    link_display = f'<a href="{invite_url}">{invite_url}</a>' if invite_url.startswith("http") else invite_url

    text = (
        f"📊 <b>Referral Status</b>\n\n"
        f"🔗 <b>Your Personal Invite Link:</b>\n"
        f"{link_display}\n\n"
        f"👥 <b>Successful Referrals:</b>\n"
        f"<b>{progress_str}</b>\n\n"
        f"📌 <b>Status:</b>\n"
        f"<b>{status_str}</b>\n\n"
        f"⏳ <b>Time Remaining:</b>\n"
        f"<b>{time_remaining_str}</b>"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_status_keyboard(group.id, invite_url=link.telegram_invite_link if link else None),
            parse_mode="HTML"
        )
        await callback.answer("✅ Status refreshed!")
    except Exception:
        await callback.answer("Status is already up to date.")


@referral_router.callback_query(F.data.startswith("tree_page:"))
async def handle_tree_page_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Handles pagination for referral trees."""
    parts = callback.data.split(":")
    group_id = int(parts[1])
    page = int(parts[2])

    ref_service = ReferralService(session, callback.bot)
    text, current_page, total_pages = await ref_service.generate_referral_tree_text(
        group_id=group_id,
        page=page
    )

    markup = get_tree_pagination_keyboard(group_id, current_page, total_pages)
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()
