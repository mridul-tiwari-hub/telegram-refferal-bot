"""Referral Requirement model."""
from datetime import datetime, timezone
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class ReferralRequirement(Base):
    __tablename__ = "referral_requirements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    required_referrals: Mapped[int] = mapped_column(Integer, default=1)
    completed_referrals: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)  # PENDING, COMPLETED, FAILED, EXEMPT
    is_exempt: Mapped[bool] = mapped_column(Boolean, default=False)
    action_taken: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
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
    user = relationship("User", back_populates="requirements")
    group = relationship("Group", back_populates="requirements")

    __table_args__ = (
        Index("ix_req_pending_deadline", "status", "deadline", "action_taken"),
    )

    def __repr__(self) -> str:
        return f"<ReferralRequirement user={self.user_id} status={self.status} {self.completed_referrals}/{self.required_referrals}>"
