"""Group Settings model."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, Boolean, DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class GroupSettings(Base):
    __tablename__ = "group_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), unique=True, nullable=False)
    referral_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    referral_deadline_hours: Mapped[int] = mapped_column(Integer, default=24)
    required_referrals: Mapped[int] = mapped_column(Integer, default=1)
    failure_action: Mapped[str] = mapped_column(String(32), default="RESTRICT")  # RESTRICT, KICK, NONE
    welcome_message: Mapped[Optional[str]] = mapped_column(
        String(1000),
        default="🎉 Welcome {first_name} to {group_name}!\nTo stay in this group, please use your referral link to invite {required_referrals} member(s) within {deadline_hours} hours."
    )
    anti_spam_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    warning_limit: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    group = relationship("Group", back_populates="settings")

    def __repr__(self) -> str:
        return f"<GroupSettings group_id={self.group_id} deadline_h={self.referral_deadline_hours} req_refs={self.required_referrals} action={self.failure_action}>"
