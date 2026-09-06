"""Unit tests for Centralized Permissions, Content Filters, Locks, Moderation, and Isolation."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from database.models.group import Group
from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from database.repositories.group_repo import GroupRepository
from database.repositories.user_repo import UserRepository
from services.permission_service import PermissionService, UserRole
from services.advanced_moderation_service import parse_duration_string, AdvancedModerationService
from services.content_filter_service import ContentFilterService
from services.lock_service import LockService
from services.activity_service import ActivityService


from bot.handlers.moderation_extra import extract_duration_and_reason, resolve_target_user


def test_parse_duration_string():
    assert parse_duration_string("10m") == 600
    assert parse_duration_string("2h") == 7200
    assert parse_duration_string("1d") == 86400
    assert parse_duration_string("1w") == 604800
    assert parse_duration_string("30s") == 30
    assert parse_duration_string("invalid") is None
    assert parse_duration_string("") is None


def test_extract_duration_and_reason():
    dur, reason = extract_duration_and_reason(["1m", "Spamming"])
    assert dur == 60
    assert reason == "Spamming"

    dur, reason = extract_duration_and_reason(["Spamming", "2h"])
    assert dur == 7200
    assert reason == "Spamming"

    dur, reason = extract_duration_and_reason(["Spamming"])
    assert dur is None
    assert reason == "Spamming"

    dur, reason = extract_duration_and_reason([], default_reason="No reason")
    assert dur is None
    assert reason == "No reason"


@pytest.mark.asyncio
async def test_resolve_target_user_reply_and_tag():
    mock_msg = MagicMock()
    mock_msg.reply_to_message.from_user.id = 7777633189
    mock_repo = AsyncMock()

    # Admin replied to D's message and typed: /mute @tofindray 1m Spanning
    args = ["@tofindray", "1m", "Spanning"]
    target_id, remaining = await resolve_target_user(mock_msg, args, mock_repo)

    assert target_id == 7777633189
    assert remaining == ["1m", "Spanning"]

    dur, reason = extract_duration_and_reason(remaining)
    assert dur == 60
    assert reason == "Spanning"


@pytest.mark.asyncio
async def test_user_role_and_rank_resolution(db_session):
    admin_repo = AdminRepository(db_session)
    group_repo = GroupRepository(db_session)
    user_repo = UserRepository(db_session)

    mock_bot = AsyncMock()

    group = await group_repo.get_or_create_group(-100999, "Test Roles")
    owner_user = await user_repo.get_or_create_user(telegram_user_id=1001, first_name="Owner")
    admin_user = await user_repo.get_or_create_user(telegram_user_id=1002, first_name="Admin")
    staff_user = await user_repo.get_or_create_user(telegram_user_id=1003, first_name="Staff")
    member_user = await user_repo.get_or_create_user(telegram_user_id=1004, first_name="Member")

    # Add staff_user as bot staff
    await admin_repo.add_staff(group.id, staff_user.id, permissions="ban,mute,warn")

    perm_service = PermissionService(db_session, mock_bot)

    # 1. Owner mock
    mock_owner_member = MagicMock()
    from aiogram.enums import ChatMemberStatus
    mock_owner_member.status = ChatMemberStatus.CREATOR
    mock_bot.get_chat_member.return_value = mock_owner_member

    role, name = await perm_service.get_user_role_and_rank(-100999, owner_user.telegram_user_id, group.id)
    assert role == UserRole.OWNER
    assert name == "Owner"

    # 2. Administrator mock
    mock_admin_member = MagicMock()
    mock_admin_member.status = ChatMemberStatus.ADMINISTRATOR
    mock_bot.get_chat_member.return_value = mock_admin_member

    role, name = await perm_service.get_user_role_and_rank(-100999, admin_user.telegram_user_id, group.id)
    assert role == UserRole.ADMIN
    assert name == "Administrator"

    # 3. Staff mock (Telegram member status is regular member, but configured as bot staff)
    mock_staff_member = MagicMock()
    mock_staff_member.status = ChatMemberStatus.MEMBER
    mock_bot.get_chat_member.return_value = mock_staff_member

    role, name = await perm_service.get_user_role_and_rank(-100999, staff_user.telegram_user_id, group.id)
    assert role == UserRole.STAFF
    assert name == "Staff"

    # 4. Ordinary member
    mock_bot.get_chat_member.return_value = mock_staff_member
    role, name = await perm_service.get_user_role_and_rank(-100999, member_user.telegram_user_id, group.id)
    assert role == UserRole.MEMBER
    assert name == "Member"


@pytest.mark.asyncio
async def test_is_admin_filter_with_staff(db_session):
    from bot.filters.admin_filter import IsAdminFilter
    from aiogram.enums import ChatMemberStatus, ChatType

    admin_repo = AdminRepository(db_session)
    group_repo = GroupRepository(db_session)
    user_repo = UserRepository(db_session)

    group = await group_repo.get_or_create_group(-100888, "Filter Group")
    staff_user = await user_repo.get_or_create_user(telegram_user_id=8801, first_name="StaffMember")
    regular_user = await user_repo.get_or_create_user(telegram_user_id=8802, first_name="RegularMember")

    await admin_repo.add_staff(group.id, staff_user.id, permissions="warn,rules")

    filter_instance = IsAdminFilter()

    # Mock message from staff
    mock_staff_msg = AsyncMock()
    mock_staff_msg.chat.type = ChatType.SUPERGROUP
    mock_staff_msg.chat.id = -100888
    mock_staff_msg.from_user.id = staff_user.telegram_user_id

    # Telegram get_member returns regular MEMBER
    tg_member = MagicMock()
    tg_member.status = ChatMemberStatus.MEMBER
    mock_staff_msg.chat.get_member.return_value = tg_member

    # Staff passes filter because they are configured as bot staff in DB!
    res_staff = await filter_instance(mock_staff_msg, session=db_session)
    assert res_staff is True

    # Regular user does not pass filter
    mock_reg_msg = AsyncMock()
    mock_reg_msg.chat.type = ChatType.SUPERGROUP
    mock_reg_msg.chat.id = -100888
    mock_reg_msg.from_user.id = regular_user.telegram_user_id
    mock_reg_msg.chat.get_member.return_value = tg_member

    res_reg = await filter_instance(mock_reg_msg, session=db_session)
    assert res_reg is False





@pytest.mark.asyncio
async def test_banned_words_exact_and_substring(db_session):
    admin_repo = AdminRepository(db_session)
    filter_service = ContentFilterService(db_session)

    group = Group(telegram_group_id=-100111, group_name="Test Group")
    db_session.add(group)
    await db_session.flush()

    # Exact word match
    await admin_repo.add_banned_word(group.id, "badword", is_substring=False)
    # Substring match
    await admin_repo.add_banned_word(group.id, "scam", is_substring=True)

    # 1. Exact match should match whole word
    violated, word = await filter_service.check_banned_words(group.id, "This is a BadWord right here")
    assert violated is True
    assert word == "badword"

    # 2. Exact match should NOT match if substring inside legitimate word
    violated, _ = await filter_service.check_banned_words(group.id, "This is notbadwordatall")
    assert violated is False

    # 3. Substring match should match inside legitimate word
    violated, word = await filter_service.check_banned_words(group.id, "check out thisscammernow")
    assert violated is True
    assert word == "scam"


@pytest.mark.asyncio
async def test_link_filter_modes_and_whitelist(db_session):
    admin_repo = AdminRepository(db_session)
    group_repo = GroupRepository(db_session)
    filter_service = ContentFilterService(db_session)

    group = await group_repo.get_or_create_group(telegram_group_id=-100222, group_name="Link Group")

    # Case 1: ALLOW_ALL by default, unless blacklisted
    violated, _ = await filter_service.check_links(group.id, "Check https://google.com")
    assert violated is False

    await admin_repo.add_domain(group.id, "malicious.com", is_allowed=False)
    violated, reason = await filter_service.check_links(group.id, "Visit http://sub.malicious.com/payload")
    assert violated is True
    assert "blacklisted" in reason

    # Case 2: TELEGRAM_ONLY mode
    await group_repo.update_settings(group.id, link_filter_mode="TELEGRAM_ONLY")
    # Telegram link should pass
    violated, _ = await filter_service.check_links(group.id, "Join our t.me/my_group link")
    assert violated is False

    # Other domain should fail unless whitelisted
    violated, _ = await filter_service.check_links(group.id, "Check https://github.com/repo")
    assert violated is True

    # Add github.com to whitelist
    await admin_repo.add_domain(group.id, "github.com", is_allowed=True)
    violated, _ = await filter_service.check_links(group.id, "Check https://github.com/repo")
    assert violated is False


@pytest.mark.asyncio
async def test_group_locks(db_session):
    admin_repo = AdminRepository(db_session)
    lock_service = LockService(db_session)

    group = Group(telegram_group_id=-100333, group_name="Lock Group")
    db_session.add(group)
    await db_session.flush()

    # Lock photos
    await admin_repo.update_locks(group.id, lock_photos=True)

    # Mock photo message
    photo_msg = MagicMock()
    photo_msg.photo = [MagicMock()]
    photo_msg.video = None
    photo_msg.animation = None
    photo_msg.sticker = None
    photo_msg.voice = None
    photo_msg.video_note = None
    photo_msg.audio = None
    photo_msg.document = None
    photo_msg.poll = None
    photo_msg.text = None
    photo_msg.caption = None

    is_locked, reason = await lock_service.is_message_locked(group.id, photo_msg)
    assert is_locked is True
    assert "Photos are locked" in reason

    # Normal text message should not be locked
    text_msg = MagicMock()
    text_msg.photo = None
    text_msg.video = None
    text_msg.animation = None
    text_msg.sticker = None
    text_msg.voice = None
    text_msg.video_note = None
    text_msg.audio = None
    text_msg.document = None
    text_msg.poll = None
    text_msg.text = "Hello everyone"
    text_msg.caption = None

    is_locked, _ = await lock_service.is_message_locked(group.id, text_msg)
    assert is_locked is False


@pytest.mark.asyncio
async def test_multi_group_isolation(db_session):
    admin_repo = AdminRepository(db_session)

    group_a = Group(telegram_group_id=-100444, group_name="Group A")
    group_b = Group(telegram_group_id=-100555, group_name="Group B")
    db_session.add_all([group_a, group_b])
    await db_session.flush()

    # Add banned word to Group A only
    await admin_repo.add_banned_word(group_a.id, "secret_a")
    # Lock text in Group B only
    await admin_repo.update_locks(group_b.id, lock_text=True)

    words_a = await admin_repo.list_banned_words(group_a.id)
    words_b = await admin_repo.list_banned_words(group_b.id)

    assert len(words_a) == 1
    assert words_a[0].word == "secret_a"
    assert len(words_b) == 0

    locks_a = await admin_repo.get_or_create_locks(group_a.id)
    locks_b = await admin_repo.get_or_create_locks(group_b.id)

    assert locks_a.lock_text is False
    assert locks_b.lock_text is True


@pytest.mark.asyncio
async def test_member_activity_tracking(db_session):
    admin_repo = AdminRepository(db_session)
    act_service = ActivityService(db_session, MagicMock())

    group = Group(telegram_group_id=-100666, group_name="Activity Group")
    user_a = User(telegram_user_id=1111, first_name="Alice")
    user_b = User(telegram_user_id=2222, first_name="Bob")
    db_session.add_all([group, user_a, user_b])
    await db_session.flush()

    # Record messages
    await act_service.record_activity(group.id, user_a.id)
    await act_service.record_activity(group.id, user_a.id)
    await act_service.record_activity(group.id, user_b.id)

    top = await admin_repo.get_top_chatters(group.id)
    assert len(top) == 2
    assert top[0].user_id == user_a.id
    assert top[0].message_count == 2
    assert top[1].user_id == user_b.id
    assert top[1].message_count == 1
