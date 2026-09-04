"""Warning model."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class Warning(Base):
    __tablename__ = "warnings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    admin_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), default="No reason specified")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    group = relationship("Group", back_populates="warnings")
    user = relationship("User", foreign_keys=[user_id], back_populates="warnings")
    admin = relationship("User", foreign_keys=[admin_user_id])

    def __repr__(self) -> str:
        return f"<Warning user_id={self.user_id} group_id={self.group_id} reason={self.reason[:20]}>"
