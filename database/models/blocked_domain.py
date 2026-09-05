"""Blocked and Whitelisted Domains model."""
from datetime import datetime, timezone
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class BlockedDomain(Base):
    __tablename__ = "blocked_domains"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=False)  # True = whitelisted, False = blacklisted
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    group = relationship("Group")

    def __repr__(self) -> str:
        return f"<BlockedDomain group_id={self.group_id} domain='{self.domain}' is_allowed={self.is_allowed}>"
