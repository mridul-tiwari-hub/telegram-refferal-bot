"""Moderation Log model."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    admin_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)  # JOIN, LEAVE, REFERRAL, DEADLINE_EXPIRED, KICK, RESTRICT, WARN, etc.
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    # Relationships
    group = relationship("Group")
    user = relationship("User", foreign_keys=[user_id])
    admin = relationship("User", foreign_keys=[admin_user_id])

    def __repr__(self) -> str:
        return f"<ModerationLog action={self.action} user_id={self.user_id} group_id={self.group_id}>"
