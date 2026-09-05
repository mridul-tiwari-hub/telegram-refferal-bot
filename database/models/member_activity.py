"""Member Activity model."""
from datetime import datetime, timezone
from sqlalchemy import Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class MemberActivity(Base):
    __tablename__ = "member_activity"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_member_activity_group_user"),
    )

    # Relationships
    group = relationship("Group")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<MemberActivity group_id={self.group_id} user_id={self.user_id} count={self.message_count}>"
