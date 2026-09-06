from typing import Optional
from aiogram import Router, F
from aiogram.types import ChatMemberUpdated, Message
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.user_repo import UserRepository
from database.repositories.group_repo import GroupRepository
from services.referral_service import ReferralService
from bot.keyboards.user_kb import get_start_bot_keyboard, get_status_keyboard
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

    # 1. Anti-raid check
    from services.raid_service import RaidService
    raid_service = RaidService(session, event.bot)
    is_raid, join_count = await raid_service.record_join_and_check_raid(group)

    # 2. Process referral attribution, create link and requirement (preserved 100%)
    req, new_link, referrer = await ref_service.handle_new_member_join(
        group=group,
        new_user=user,
        telegram_invite_link_str=invite_link_str
    )

    # 3. If raid mode active, restrict user immediately
    if group_settings.raid_mode or is_raid:
        try:
            from aiogram.types import ChatPermissions
            await event.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=new_member.id,
                permissions=ChatPermissions(can_send_messages=False)
            )
            logger.info(f"User {new_member.id} restricted due to active raid mode in {chat.id}")
        except Exception as e:
            logger.debug(f"Failed to restrict user during raid: {e}")
        return

    # 4. If Captcha verification enabled, issue verification challenge
    if group_settings.captcha_enabled:
        from services.captcha_service import CaptchaService
        captcha_service = CaptchaService(session, event.bot)
        await captcha_service.prompt_captcha(group, user)

    # 5. Send Welcome Message in group if enabled
    if group_settings.welcome_enabled:
        bot_info = await event.bot.get_me()
        welcome_template = group_settings.welcome_message or "🎉 Welcome {first_name} to {group_name}!"
        welcome_text = welcome_template.format(
            first_name=user.first_name,
            last_name=user.last_name or "",
            username=f"@{user.username}" if user.username else user.first_name,
            user_id=user.telegram_user_id,
            group_name=group.group_name,
            group=group.group_name,
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
            link_url = new_link.telegram_invite_link
            link_display = f'<a href="{link_url}">{link_url}</a>' if link_url.startswith("http") else link_url
            await event.bot.send_message(
                chat_id=new_member.id,
                text=(
                    f"🎉 <b>Welcome to {group.group_name}!</b>\n\n"
                    f"🔗 <b>Your Personal Referral Link:</b>\n"
                    f"{link_display}\n\n"
                    f"Share this link with your friends to complete your referral requirement."
                ),
                reply_markup=get_status_keyboard(group.id, invite_url=link_url),
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


@members_router.message(F.new_chat_members)
async def on_new_chat_members_message(message: Message, session: AsyncSession) -> None:
    """Fallback handler when Telegram sends new_chat_members service message."""
    if not message.new_chat_members:
        return

    chat = message.chat
    user_repo = UserRepository(session)
    group_repo = GroupRepository(session)
    ref_service = ReferralService(session, message.bot)

    group = await group_repo.get_or_create_group(
        telegram_group_id=chat.id,
        group_name=chat.title or "Telegram Group"
    )

    for new_member in message.new_chat_members:
        if new_member.is_bot:
            continue

        logger.info(f"User {new_member.id} ({new_member.full_name}) joined chat {chat.id} via new_chat_members")

        user = await user_repo.get_or_create_user(
            telegram_user_id=new_member.id,
            username=new_member.username,
            first_name=new_member.first_name,
            last_name=new_member.last_name
        )

        await ref_service.handle_new_member_join(
            group=group,
            new_user=user,
            telegram_invite_link_str=None
        )


@members_router.message(F.left_chat_member)
async def on_left_chat_member_message(message: Message, session: AsyncSession) -> None:
    """Fallback handler when Telegram sends left_chat_member service message."""
    if not message.left_chat_member or message.left_chat_member.is_bot:
        return

    user_repo = UserRepository(session)
    await user_repo.mark_left(message.left_chat_member.id)
