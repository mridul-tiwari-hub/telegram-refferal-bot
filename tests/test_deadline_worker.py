"""Test background deadline worker and moderation actions."""
from datetime import datetime, timedelta, timezone
import pytest
from database.repositories.user_repo import UserRepository
from database.repositories.group_repo import GroupRepository
from database.repositories.referral_repo import ReferralRepository
from services.deadline_service import DeadlineService


@pytest.mark.asyncio
async def test_deadline_expiration_and_kick(db_session, mock_bot):
    user_repo = UserRepository(db_session)
    group_repo = GroupRepository(db_session)
    referral_repo = ReferralRepository(db_session)

    group = await group_repo.get_or_create_group(telegram_group_id=-1001234567890, group_name="Test Group")
    await group_repo.update_settings(group.id, failure_action="KICK")

    user = await user_repo.get_or_create_user(telegram_user_id=3333, first_name="Charlie")

    # Create expired requirement (deadline in the past)
    past_deadline = datetime.now(timezone.utc) - timedelta(hours=2)
    req = await referral_repo.create_requirement(user.id, group.id, deadline=past_deadline, required_referrals=1)

    deadline_service = DeadlineService(db_session, mock_bot)
    processed = await deadline_service.check_and_process_expired_deadlines()

    assert processed == 1
    # Verify kick was called (ban + unban)
    mock_bot.ban_chat_member.assert_called_once_with(
        chat_id=group.telegram_group_id,
        user_id=user.telegram_user_id
    )
    mock_bot.unban_chat_member.assert_called_once_with(
        chat_id=group.telegram_group_id,
        user_id=user.telegram_user_id,
        only_if_banned=True
    )

    # Verify requirement marked as action_taken
    req_updated = await referral_repo.get_requirement(user.id, group.id)
    assert req_updated.action_taken is True
    assert req_updated.status == "FAILED"

    # Verify idempotence: second run processes 0
    processed_again = await deadline_service.check_and_process_expired_deadlines()
    assert processed_again == 0


@pytest.mark.asyncio
async def test_deadline_restrict_action(db_session, mock_bot):
    user_repo = UserRepository(db_session)
    group_repo = GroupRepository(db_session)
    referral_repo = ReferralRepository(db_session)

    group = await group_repo.get_or_create_group(telegram_group_id=-1001234567891, group_name="Restrict Group")
    await group_repo.update_settings(group.id, failure_action="RESTRICT")

    user = await user_repo.get_or_create_user(telegram_user_id=4444, first_name="Dave")

    past_deadline = datetime.now(timezone.utc) - timedelta(minutes=10)
    await referral_repo.create_requirement(user.id, group.id, deadline=past_deadline, required_referrals=1)

    deadline_service = DeadlineService(db_session, mock_bot)
    processed = await deadline_service.check_and_process_expired_deadlines()

    assert processed == 1
    mock_bot.restrict_chat_member.assert_called_once()

    req_updated = await referral_repo.get_requirement(user.id, group.id)
    assert req_updated.action_taken is True
    assert req_updated.status == "FAILED"
