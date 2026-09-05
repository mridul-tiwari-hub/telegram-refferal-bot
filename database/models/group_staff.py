"""Group Staff model."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class GroupStaff(Base):
    __tablename__ = "group_staff"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permissions: Mapped[str] = mapped_column(
        Text,
        default="ban,mute,warn,delete,filters,locks,welcome,rules,stats,referrals,settings"
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    group = relationship("Group")
    user = relationship("User", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])

    def has_permission(self, perm: str) -> bool:
        if not self.permissions:
            return False
        perms = [p.strip().lower() for p in self.permissions.split(",")]
        return "*" in perms or perm.lower() in perms

    def __repr__(self) -> str:
        return f"<GroupStaff group_id={self.group_id} user_id={self.user_id} permissions={self.permissions}>"
