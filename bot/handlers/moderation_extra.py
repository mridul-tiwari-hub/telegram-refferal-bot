"""Extended Moderation Handlers for Ban, Mute, Unban, Unmute, and History."""
from typing import Optional, Tuple
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.group_repo import GroupRepository
from database.repositories.user_repo import UserRepository
from database.repositories.admin_repo import AdminRepository
from database.repositories.moderation_repo import ModerationRepository
from database.models.group import Group
from database.models.user import User
from services.permission_service import PermissionService
from services.advanced_moderation_service import AdvancedModerationService, parse_duration_string
from utils.logging import get_logger

logger = get_logger(__name__)
moderation_extra_router = Router(name="moderation_extra_router")


async def resolve_target_user(
    message: Message,
    args: list[str],
    user_repo: UserRepository
) -> Tuple[Optional[int], list[str]]:
    """Resolves target user Telegram ID from reply, username, or ID string."""
    target_id: Optional[int] = None
    remaining_args = list(args)

    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        # If user explicitly provided a target token (@username or numerical id) while replying,
        # consume it from remaining_args so it does not get treated as duration or reason.
        if remaining_args:
            first = remaining_args[0]
            if first.startswith("@"):
                remaining_args.pop(0)
            else:
                try:
                    int(first)
                    remaining_args.pop(0)
                except ValueError:
                    pass
        return target_id, remaining_args

    if remaining_args:
        first = remaining_args[0]
        if first.startswith("@"):
            username = first.lstrip("@")
            user = await user_repo.get_by_username(username)
            if user:
                target_id = user.telegram_user_id
                remaining_args.pop(0)
        else:
            try:
                target_id = int(first)
                remaining_args.pop(0)
            except ValueError:
                pass

    return target_id, remaining_args


def extract_duration_and_reason(
    remaining_args: list[str],
    default_reason: str = "Action by administrator"
) -> Tuple[Optional[int], str]:
    """
    Finds duration anywhere in arguments (e.g. '1m', '2h', '1d', '30s').
    The remaining non-duration arguments are combined into the reason.
    """
    duration_seconds: Optional[int] = None
    reason_tokens: list[str] = []

    for token in remaining_args:
        if duration_seconds is None:
            dur = parse_duration_string(token)
            if dur is not None:
                duration_seconds = dur
                continue
        reason_tokens.append(token)

    reason = " ".join(reason_tokens).strip() if reason_tokens else default_reason
    return duration_seconds, reason


@moderation_extra_router.message(Command("ban"))
async def handle_ban(message: Message, session: AsyncSession) -> None:
    """Bans a member permanently or temporarily."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    perm_service = PermissionService(session, message.bot)
    mod_service = AdvancedModerationService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    tokens = message.text.split()[1:]
    target_tg_id, remaining = await resolve_target_user(message, tokens, user_repo)

    if not target_tg_id:
        await message.answer("Usage: <code>/ban &lt;USER&gt; [DURATION: e.g. 10m, 2h, 1d] [REASON]</code> or reply to a message.", parse_mode="HTML")
        return

    # Check permissions & hierarchy
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="ban",
        target_tg_id=target_tg_id,
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    # Parse duration (e.g. 10m, 2h, 1d) and reason
    duration_seconds, ban_reason = extract_duration_and_reason(remaining, default_reason="Banned by administrator")

    target_user = await user_repo.get_or_create_user(telegram_user_id=target_tg_id)
    actor_user = await user_repo.get_or_create_user(telegram_user_id=message.from_user.id)

    success, reply_msg = await mod_service.ban_member(
        group=group,
        target_user=target_user,
        actor_user=actor_user,
        duration_seconds=duration_seconds,
        reason=ban_reason
    )
    await message.answer(f"{'✅' if success else '❌'} {reply_msg}", parse_mode="HTML")


@moderation_extra_router.message(Command("unban"))
async def handle_unban(message: Message, session: AsyncSession) -> None:
    """Unbans a member so they can rejoin."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    perm_service = PermissionService(session, message.bot)
    mod_service = AdvancedModerationService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    tokens = message.text.split()[1:]
    target_tg_id, _ = await resolve_target_user(message, tokens, user_repo)

    if not target_tg_id:
        await message.answer("Usage: <code>/unban &lt;USER_ID&gt;</code> or reply to user.", parse_mode="HTML")
        return

    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="unban",
        target_tg_id=target_tg_id,
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    target_user = await user_repo.get_or_create_user(telegram_user_id=target_tg_id)
    actor_user = await user_repo.get_or_create_user(telegram_user_id=message.from_user.id)

    success, reply_msg = await mod_service.unban_member(group, target_user, actor_user)
    await message.answer(f"{'✅' if success else '❌'} {reply_msg}", parse_mode="HTML")


@moderation_extra_router.message(Command("mute"))
async def handle_mute(message: Message, session: AsyncSession) -> None:
    """Mutes a member permanently or temporarily."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    perm_service = PermissionService(session, message.bot)
    mod_service = AdvancedModerationService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    tokens = message.text.split()[1:]
    target_tg_id, remaining = await resolve_target_user(message, tokens, user_repo)

    if not target_tg_id:
        await message.answer("Usage: <code>/mute &lt;USER&gt; [DURATION: e.g. 10m, 2h, 1d] [REASON]</code> or reply.", parse_mode="HTML")
        return

    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="mute",
        target_tg_id=target_tg_id,
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    # Parse duration (e.g. 10m, 2h, 1d) and reason
    duration_seconds, mute_reason = extract_duration_and_reason(remaining, default_reason="Muted by administrator")

    target_user = await user_repo.get_or_create_user(telegram_user_id=target_tg_id)
    actor_user = await user_repo.get_or_create_user(telegram_user_id=message.from_user.id)

    success, reply_msg = await mod_service.mute_member(
        group=group,
        target_user=target_user,
        actor_user=actor_user,
        duration_seconds=duration_seconds,
        reason=mute_reason
    )
    await message.answer(f"{'✅' if success else '❌'} {reply_msg}", parse_mode="HTML")


@moderation_extra_router.message(Command("unmute"))
async def handle_unmute(message: Message, session: AsyncSession) -> None:
    """Unmutes a member."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    perm_service = PermissionService(session, message.bot)
    mod_service = AdvancedModerationService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    tokens = message.text.split()[1:]
    target_tg_id, _ = await resolve_target_user(message, tokens, user_repo)

    if not target_tg_id:
        await message.answer("Usage: <code>/unmute &lt;USER_ID&gt;</code> or reply to user.", parse_mode="HTML")
        return

    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="unmute",
        target_tg_id=target_tg_id,
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    target_user = await user_repo.get_or_create_user(telegram_user_id=target_tg_id)
    actor_user = await user_repo.get_or_create_user(telegram_user_id=message.from_user.id)

    success, reply_msg = await mod_service.unmute_member(group, target_user, actor_user)
    await message.answer(f"{'✅' if success else '❌'} {reply_msg}", parse_mode="HTML")


@moderation_extra_router.message(Command("banlist"))
async def handle_banlist(message: Message, session: AsyncSession) -> None:
    """Displays active temporary bans in this group."""
    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    group = await group_repo.get_by_telegram_id(message.chat.id)
    if not group:
        return

    from database.models.temporary_action import TemporaryAction
    from sqlalchemy import select, and_
    stmt = select(TemporaryAction).where(
        and_(
            TemporaryAction.group_id == group.id,
            TemporaryAction.action_type == "BAN",
            TemporaryAction.is_active.is_(True)
        )
    )
    res = await session.execute(stmt)
    bans = list(res.scalars().all())

    if not bans:
        await message.answer("📋 <i>No active temporary bans recorded in this group.</i>", parse_mode="HTML")
        return

    lines = [f"🔨 <b>ACTIVE TEMPORARY BANS ({len(bans)})</b>\n"]
    for idx, b in enumerate(bans, 1):
        target = await session.get(User, b.user_id)
        tg_id = target.telegram_user_id if target else b.user_id
        exp = b.expires_at.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"{idx}. User <code>{tg_id}</code> — Until: <i>{exp}</i> (Reason: {b.reason or 'None'})")

    await message.answer("\n".join(lines), parse_mode="HTML")


@moderation_extra_router.message(Command("mutelist"))
async def handle_mutelist(message: Message, session: AsyncSession) -> None:
    """Displays active temporary mutes in this group."""
    group_repo = GroupRepository(session)
    group = await group_repo.get_by_telegram_id(message.chat.id)
    if not group:
        return

    from database.models.temporary_action import TemporaryAction
    from sqlalchemy import select, and_
    stmt = select(TemporaryAction).where(
        and_(
            TemporaryAction.group_id == group.id,
            TemporaryAction.action_type == "MUTE",
            TemporaryAction.is_active.is_(True)
        )
    )
    res = await session.execute(stmt)
    mutes = list(res.scalars().all())

    if not mutes:
        await message.answer("📋 <i>No active temporary mutes recorded in this group.</i>", parse_mode="HTML")
        return

    lines = [f"🔇 <b>ACTIVE TEMPORARY MUTES ({len(mutes)})</b>\n"]
    for idx, m in enumerate(mutes, 1):
        target = await session.get(User, m.user_id)
        tg_id = target.telegram_user_id if target else m.user_id
        exp = m.expires_at.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"{idx}. User <code>{tg_id}</code> — Until: <i>{exp}</i> (Reason: {m.reason or 'None'})")

    await message.answer("\n".join(lines), parse_mode="HTML")


@moderation_extra_router.message(Command("history"))
async def handle_history(message: Message, session: AsyncSession) -> None:
    """Displays moderation history for a user in the group."""
    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    mod_repo = ModerationRepository(session)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    tokens = message.text.split()[1:]
    target_tg_id, _ = await resolve_target_user(message, tokens, user_repo)

    if not target_tg_id:
        await message.answer("Usage: <code>/history &lt;USER&gt;</code> or reply to a message.", parse_mode="HTML")
        return

    target_user = await user_repo.get_by_telegram_id(target_tg_id)
    if not target_user:
        await message.answer("User record not found in database.")
        return

    # Fetch warnings
    warnings = await mod_repo.get_warnings(group.id, target_user.id)
    # Fetch moderation logs for this user
    from database.models.moderation_log import ModerationLog
    from sqlalchemy import select, desc
    stmt = (
        select(ModerationLog)
        .where(ModerationLog.group_id == group.id, ModerationLog.user_id == target_user.id)
        .order_by(desc(ModerationLog.created_at))
        .limit(10)
    )
    res = await session.execute(stmt)
    logs = list(res.scalars().all())

    lines = [
        f"📜 <b>MODERATION HISTORY FOR {target_user.first_name}</b> [<code>{target_user.telegram_user_id}</code>]\n",
        f"• Active Warnings: <b>{len(warnings)}</b>",
        f"• Total Logged Events: <b>{len(logs)}</b>\n",
        "<b>Recent Actions:</b>"
    ]

    if not logs:
        lines.append("<i>Clean record — No moderation actions recorded.</i>")
    else:
        for l in logs:
            dt = l.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"• [<b>{l.action}</b>] {dt} — <i>{l.details or 'No details'}</i>")

    await message.answer("\n".join(lines), parse_mode="HTML")
