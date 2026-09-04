"""Test referral attribution and relationships."""
import pytest
from database.repositories.user_repo import UserRepository
from database.repositories.group_repo import GroupRepository
from database.repositories.referral_repo import ReferralRepository
from services.referral_service import ReferralService
from services.invite_link_service import InviteLinkService


@pytest.mark.asyncio
async def test_referral_attribution_and_completion(db_session, mock_bot):
    user_repo = UserRepository(db_session)
    group_repo = GroupRepository(db_session)
    referral_repo = ReferralRepository(db_session)
    invite_service = InviteLinkService(db_session, mock_bot)
    ref_service = ReferralService(db_session, mock_bot)

    # 1. Setup group & member A (the referrer)
    group = await group_repo.get_or_create_group(telegram_group_id=-1001234567890, group_name="Test Group")
    user_a = await user_repo.get_or_create_user(telegram_user_id=1111, first_name="Alice")

    # Generate invite link for Alice
    link_a = await invite_service.get_or_create_referral_link(user_a, group)
    assert link_a is not None
    assert link_a.telegram_invite_link == "https://t.me/+MockTestInviteLink123"

    # Alice has requirement of 1 referral
    from datetime import datetime, timedelta, timezone
    deadline = datetime.now(timezone.utc) + timedelta(hours=24)
    req_a = await referral_repo.create_requirement(user_a.id, group.id, deadline=deadline, required_referrals=1)
    assert req_a.status == "PENDING"
    assert req_a.completed_referrals == 0

    # 2. Member B joins using Alice's invite link
    user_b = await user_repo.get_or_create_user(telegram_user_id=2222, first_name="Bob")
    req_b, link_b, referrer = await ref_service.handle_new_member_join(
        group=group,
        new_user=user_b,
        telegram_invite_link_str=link_a.telegram_invite_link
    )

    # Assert Alice received referral credit and completed requirement
    req_a_updated = await referral_repo.get_requirement(user_a.id, group.id)
    assert req_a_updated.completed_referrals == 1
    assert req_a_updated.status == "COMPLETED"
    assert referrer.id == user_a.id

    # Assert Bob has his own requirement created
    assert req_b is not None
    assert req_b.status == "PENDING"
    assert req_b.completed_referrals == 0


@pytest.mark.asyncio
async def test_duplicate_referral_prevention(db_session, mock_bot):
    user_repo = UserRepository(db_session)
    group_repo = GroupRepository(db_session)
    referral_repo = ReferralRepository(db_session)
    invite_service = InviteLinkService(db_session, mock_bot)
    ref_service = ReferralService(db_session, mock_bot)

    group = await group_repo.get_or_create_group(telegram_group_id=-1001234567890, group_name="Test Group")
    user_a = await user_repo.get_or_create_user(telegram_user_id=1111, first_name="Alice")
    link_a = await invite_service.get_or_create_referral_link(user_a, group)

    from datetime import datetime, timedelta, timezone
    deadline = datetime.now(timezone.utc) + timedelta(hours=24)
    await referral_repo.create_requirement(user_a.id, group.id, deadline=deadline, required_referrals=2)

    user_b = await user_repo.get_or_create_user(telegram_user_id=2222, first_name="Bob")

    # First join
    await ref_service.handle_new_member_join(group, user_b, link_a.telegram_invite_link)
    req_a = await referral_repo.get_requirement(user_a.id, group.id)
    assert req_a.completed_referrals == 1

    # Second join by same user (e.g. rejoined after leaving)
    await ref_service.handle_new_member_join(group, user_b, link_a.telegram_invite_link)
    req_a_after = await referral_repo.get_requirement(user_a.id, group.id)

    # Should STILL be 1, no duplicate credit awarded!
    assert req_a_after.completed_referrals == 1
