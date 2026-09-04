"""Test referral code generation and security utilities."""
from datetime import datetime, timedelta, timezone
from utils.security import generate_referral_code, format_time_remaining


def test_referral_code_uniqueness():
    codes = set()
    for _ in range(1000):
        code = generate_referral_code(length=6)
        assert len(code) == 6
        assert code.isalnum()
        assert code == code.upper()
        codes.add(code)

    # 1000 random 6-character alphanumeric codes should virtually never collide
    assert len(codes) == 1000


def test_format_time_remaining_future():
    future = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    formatted, is_expired = format_time_remaining(future)
    assert not is_expired
    assert "5 hours" in formatted or "6 hours" in formatted


def test_format_time_remaining_expired():
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    formatted, is_expired = format_time_remaining(past)
    assert is_expired
    assert "Expired" in formatted
