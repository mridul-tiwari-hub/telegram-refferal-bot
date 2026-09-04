"""Test warning system, exemptions, and moderation."""
from datetime import datetime, timedelta, timezone
import pytest
from database.repositories.user_repo import UserRepository
from database.repositories.group_repo import GroupRepository
from database.repositories.referral_repo import ReferralRepository
from services.warning_service import WarningService
from services.member_service import MemberService
from services.deadline_service import DeadlineService


@pytest.mark.asyncio
async def test_warning_limit_action(db_session, mock_bot):
    user_repo = UserRepository(db_session)
    group_repo = GroupRepository(db_session)
    warning_service = WarningService(db_session, mock_bot)

    group = await group_repo.get_or_create_group(telegram_group_id=-1001234567892, group_name="Warn Group")
    await group_repo.update_settings(group.id, warning_limit=2, failure_action="RESTRICT")

    user = await user_repo.get_or_create_user(telegram_user_id=5555, first_name="Eve")

    # Warning 1: limit not reached
    _, count1, limit1, action1 = await warning_service.issue_warning(group, user, admin_user_id=None, reason="Spam")
    assert count1 == 1
    assert limit1 == 2
    assert action1 is False

    # Warning 2: limit reached, trigger moderation action
    _, count2, limit2, action2 = await warning_service.issue_warning(group, user, admin_user_id=None, reason="Flood")
    assert count2 == 2
    assert action2 is True
    mock_bot.restrict_chat_member.assert_called_once()


@pytest.mark.asyncio
async def test_exemption_protects_from_deadline(db_session, mock_bot):
    user_repo = UserRepository(db_session)
    group_repo = GroupRepository(db_session)
    referral_repo = ReferralRepository(db_session)
    member_service = MemberService(db_session, mock_bot)
    deadline_service = DeadlineService(db_session, mock_bot)

    group = await group_repo.get_or_create_group(telegram_group_id=-1001234567893, group_name="Exempt Group")
    user = await user_repo.get_or_create_user(telegram_user_id=6666, first_name="Frank")

    past_deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    await referral_repo.create_requirement(user.id, group.id, deadline=past_deadline, required_referrals=1)

    # Exempt Frank
    await member_service.exempt_member(user, group, is_exempt=True, admin_id=None)

    # Run deadline check
    processed = await deadline_service.check_and_process_expired_deadlines()

    # Frank is exempt, so no kick/restrict moderation action is executed
    assert processed == 0
    mock_bot.ban_chat_member.assert_not_called()
    mock_bot.restrict_chat_member.assert_not_called()
