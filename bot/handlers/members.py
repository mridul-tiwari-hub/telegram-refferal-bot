"""Member Join and Leave Event Handlers."""
from typing import Optional
from aiogram import Router, F
from aiogram.types import ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.user_repo import UserRepository
from database.repositories.group_repo import GroupRepository
from services.referral_service import ReferralService
from bot.keyboards.user_kb import get_start_bot_keyboard
from utils.logging import get_logger

logger = get_logger(__name__)
members_router = Router(name="members_router")


@members_router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_user_join(event: ChatMemberUpdated, session: AsyncSession) -> None:
    """
    Triggered when a member joins the chat.
    Attribution is handled using event.invite_link.
    """
    chat = event.chat
    new_member = event.new_chat_member.user

    # Skip if bot itself joined
    if new_member.is_bot:
        return

    logger.info(f"User {new_member.id} ({new_member.full_name}) joined chat {chat.id}")

    user_repo = UserRepository(session)
    group_repo = GroupRepository(session)
    ref_service = ReferralService(session, event.bot)

    # Register/update user and group
    user = await user_repo.get_or_create_user(
        telegram_user_id=new_member.id,
        username=new_member.username,
        first_name=new_member.first_name,
        last_name=new_member.last_name
    )

    group = await group_repo.get_or_create_group(
        telegram_group_id=chat.id,
        group_name=chat.title or "Telegram Group"
    )
    group_settings = await group_repo.get_settings(group.id)

    # Detect invite link used to join
    invite_link_str: Optional[str] = None
    if event.invite_link and event.invite_link.invite_link:
        invite_link_str = event.invite_link.invite_link
        logger.info(f"Join invite link detected: {invite_link_str}")

    # Process referral attribution, create link and requirement
    req, new_link, referrer = await ref_service.handle_new_member_join(
        group=group,
        new_user=user,
        telegram_invite_link_str=invite_link_str
    )

    # Send Welcome Message in group with fallback button
    bot_info = await event.bot.get_me()
    welcome_template = group_settings.welcome_message or "🎉 Welcome {first_name} to {group_name}!"
    welcome_text = welcome_template.format(
        first_name=user.first_name,
        username=f"@{user.username}" if user.username else user.first_name,
        group_name=group.group_name,
        required_referrals=group_settings.required_referrals,
        deadline_hours=group_settings.referral_deadline_hours
    )

    # Mention referrer if attributed
    if referrer:
        ref_name = f"@{referrer.username}" if referrer.username else referrer.first_name
        welcome_text += f"\n\n👤 Referred by: <b>{ref_name}</b>"

    if group_settings.referral_enabled:
        welcome_text += (
            f"\n\n⚠️ <i>Requirement:</i> Invite <b>{group_settings.required_referrals}</b> member(s) "
            f"within <b>{group_settings.referral_deadline_hours} hours</b> to stay in the group.\n"
            f"Click the button below to get your personal referral link!"
        )

    reply_markup = get_start_bot_keyboard(bot_info.username, group.id)

    try:
        await event.bot.send_message(
            chat_id=chat.id,
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to send welcome message: {e}")

    # Attempt to private message the user directly (works only if user had previously started bot)
    if new_link:
        try:
            await event.bot.send_message(
                chat_id=new_member.id,
                text=(
                    f"🎉 <b>Welcome to {group.group_name}!</b>\n\n"
                    f"🔗 <b>Your Personal Referral Link:</b>\n"
                    f"<code>{new_link.telegram_invite_link}</code>\n\n"
                    f"Share this link with your friends to complete your referral requirement."
                ),
                parse_mode="HTML"
            )
        except Exception:
            # Expected fallback: User has not initiated the bot yet.
            pass


@members_router.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def on_user_leave(event: ChatMemberUpdated, session: AsyncSession) -> None:
    """Triggered when a member leaves or is removed."""
    user = event.old_chat_member.user
    if user.is_bot:
        return

    logger.info(f"User {user.id} left chat {event.chat.id}")
    user_repo = UserRepository(session)
    await user_repo.mark_left(user.id)
