"""Referral Relationship model."""
from datetime import datetime, timezone
from sqlalchemy import Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class ReferralRelationship(Base):
    __tablename__ = "referral_relationships"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    referrer_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    referred_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    invite_link_id: Mapped[int] = mapped_column(Integer, ForeignKey("referral_invite_links.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    referrer = relationship("User", foreign_keys=[referrer_user_id])
    referred = relationship("User", foreign_keys=[referred_user_id])
    group = relationship("Group")
    invite_link = relationship("ReferralInviteLink", back_populates="relationships")

    __table_args__ = (
        UniqueConstraint("group_id", "referred_user_id", name="uq_group_referred_user"),
    )

    def __repr__(self) -> str:
        return f"<ReferralRelationship referrer={self.referrer_user_id} -> referred={self.referred_user_id}>"
