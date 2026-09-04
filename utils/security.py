"""Cryptographic security, referral code generation, and time formatting utilities."""
import secrets
import string
from datetime import datetime, timezone
from typing import Tuple


REFERRAL_ALPHABET = string.ascii_uppercase + string.digits


def generate_referral_code(length: int = 6) -> str:
    """
    Generates a cryptographically secure, unpredictable alphanumeric referral code.
    Example: AB7K29, X9F3LM, P2K8ZQ
    """
    return "".join(secrets.choice(REFERRAL_ALPHABET) for _ in range(length))


def format_time_remaining(deadline: datetime) -> Tuple[str, bool]:
    """
    Calculates remaining time until deadline in a user-friendly format.
    Returns: (formatted_string, is_expired)
    """
    # Ensure timezone awareness (UTC)
    now = datetime.now(timezone.utc)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    diff = deadline - now
    total_seconds = int(diff.total_seconds())

    if total_seconds <= 0:
        return "Expired (0 minutes remaining)", True

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"{hours} hours {minutes} minutes", False
    else:
        return f"{minutes} minutes", False
