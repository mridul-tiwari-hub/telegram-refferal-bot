"""Structured logging setup."""
import sys
import logging
from typing import Optional


def setup_logging(level: int = logging.INFO) -> None:
    """Configures application-wide logging format."""
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Silence overly verbose libraries
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Returns a logger instance."""
    return logging.getLogger(name or "telegram_referral_bot")
