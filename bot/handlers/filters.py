"""Word and Link Filter Command Handlers."""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.group_repo import GroupRepository
from database.repositories.admin_repo import AdminRepository
from services.permission_service import PermissionService, UserRole
from utils.logging import get_logger

logger = get_logger(__name__)
filters_router = Router(name="filters_router")


@filters_router.message(Command("addword"))
async def handle_addword(message: Message, session: AsyncSession) -> None:
    """Adds a banned word or phrase to the filter."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="filters",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    tokens = message.text.split(maxsplit=2)
    if len(tokens) < 2:
        await message.answer("Usage: <code>/addword &lt;WORD/PHRASE&gt; [substring]</code>", parse_mode="HTML")
        return

    word = tokens[1]
    is_sub = len(tokens) > 2 and tokens[2].lower() in ["sub", "substring", "true", "1"]

    bw = await admin_repo.add_banned_word(group.id, word, is_substring=is_sub)
    await perm_service.log_action(
        group=group,
        actor_tg_id=message.from_user.id,
        action="ADD_BANNED_WORD",
        details=f"Word: {bw.word} (Substring: {bw.is_substring})"
    )
    await message.answer(f"✅ Added banned word: <code>{bw.word}</code> (Match substring: <b>{bw.is_substring}</b>).", parse_mode="HTML")


@filters_router.message(Command("delword"))
async def handle_delword(message: Message, session: AsyncSession) -> None:
    """Removes a banned word from the filter."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="filters",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    tokens = message.text.split(maxsplit=1)
    if len(tokens) < 2:
        await message.answer("Usage: <code>/delword &lt;WORD&gt;</code>", parse_mode="HTML")
        return

    word = tokens[1]
    deleted = await admin_repo.remove_banned_word(group.id, word)
    if deleted:
        await message.answer(f"✅ Removed <code>{word}</code> from banned words list.", parse_mode="HTML")
    else:
        await message.answer(f"Word <code>{word}</code> was not found in banned words list.", parse_mode="HTML")


@filters_router.message(Command("badwords"))
@filters_router.message(Command("bannedwords"))
async def handle_listwords(message: Message, session: AsyncSession) -> None:
    """Lists all banned words for the group."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")

    words = await admin_repo.list_banned_words(group.id)
    if not words:
        await message.answer("🚫 <i>No banned words configured for this group.</i>", parse_mode="HTML")
        return

    lines = [f"🚫 <b>BANNED WORDS ({len(words)}) — {group.group_name}</b>\n"]
    for idx, bw in enumerate(words, 1):
        sub_badge = " [substring]" if bw.is_substring else ""
        lines.append(f"{idx}. <code>{bw.word}</code>{sub_badge}")

    await message.answer("\n".join(lines), parse_mode="HTML")


@filters_router.message(Command("clearwords"))
async def handle_clearwords(message: Message, session: AsyncSession) -> None:
    """Clears all banned words for the group."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="filters",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    cleared = await admin_repo.clear_banned_words(group.id)
    await message.answer(f"✅ Cleared all <b>{cleared}</b> banned words.", parse_mode="HTML")


@filters_router.message(Command("allowlink"))
async def handle_allowlink(message: Message, session: AsyncSession) -> None:
    """Adds a domain to whitelist."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="filters",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    tokens = message.text.split()
    if len(tokens) < 2:
        await message.answer("Usage: <code>/allowlink &lt;domain.com&gt;</code>", parse_mode="HTML")
        return

    domain = tokens[1]
    await admin_repo.add_domain(group.id, domain, is_allowed=True)
    await message.answer(f"✅ Whitelisted domain: <code>{domain}</code>", parse_mode="HTML")


@filters_router.message(Command("blocklink"))
async def handle_blocklink(message: Message, session: AsyncSession) -> None:
    """Adds a domain to blacklist."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="filters",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    tokens = message.text.split()
    if len(tokens) < 2:
        await message.answer("Usage: <code>/blocklink &lt;domain.com&gt;</code>", parse_mode="HTML")
        return

    domain = tokens[1]
    await admin_repo.add_domain(group.id, domain, is_allowed=False)
    await message.answer(f"🚫 Blacklisted domain: <code>{domain}</code>", parse_mode="HTML")


@filters_router.message(Command("links"))
async def handle_links_status(message: Message, session: AsyncSession) -> None:
    """Displays current link filtering configuration."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    admin_repo = AdminRepository(session)
    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    settings = await group_repo.get_settings(group.id)

    domains = await admin_repo.list_domains(group.id)
    whitelist = [d.domain for d in domains if d.is_allowed]
    blacklist = [d.domain for d in domains if not d.is_allowed]

    text = (
        f"🔗 <b>LINK FILTER SETTINGS — {group.group_name}</b>\n\n"
        f"• Link Filter Mode: <b>{settings.link_filter_mode}</b>\n"
        f"• Allowed (Whitelisted) Domains ({len(whitelist)}): <code>{', '.join(whitelist) if whitelist else 'None'}</code>\n"
        f"• Blocked (Blacklisted) Domains ({len(blacklist)}): <code>{', '.join(blacklist) if blacklist else 'None'}</code>\n\n"
        f"Change mode: <code>/setlinkmode ALLOW_ALL | BLOCK_ALL | TELEGRAM_ONLY</code>"
    )
    await message.answer(text, parse_mode="HTML")


@filters_router.message(Command("setlinkmode"))
async def handle_setlinkmode(message: Message, session: AsyncSession) -> None:
    """Sets link filter mode."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="filters",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    tokens = message.text.split()
    if len(tokens) < 2 or tokens[1].upper() not in ["ALLOW_ALL", "BLOCK_ALL", "TELEGRAM_ONLY"]:
        await message.answer("Usage: <code>/setlinkmode ALLOW_ALL | BLOCK_ALL | TELEGRAM_ONLY</code>", parse_mode="HTML")
        return

    mode = tokens[1].upper()
    await group_repo.update_settings(group.id, link_filter_mode=mode)
    await message.answer(f"✅ Link filter mode updated to <b>{mode}</b>.", parse_mode="HTML")
