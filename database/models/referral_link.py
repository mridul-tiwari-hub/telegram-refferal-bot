"""Referral Invite Link model."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class ReferralInviteLink(Base):
    __tablename__ = "referral_invite_links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    referral_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    telegram_invite_link: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="invite_links")
    group = relationship("Group", back_populates="invite_links")
    relationships = relationship("ReferralRelationship", back_populates="invite_link")

    __table_args__ = (
        Index("ix_referral_link_group_user", "group_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<ReferralInviteLink code={self.referral_code} user_id={self.user_id} count={self.usage_count}>"
