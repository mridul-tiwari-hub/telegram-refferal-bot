"""User model."""
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import BigInteger, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), default="")
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    invite_links = relationship("ReferralInviteLink", back_populates="user", cascade="all, delete-orphan")
    requirements = relationship("ReferralRequirement", back_populates="user", cascade="all, delete-orphan")
    warnings = relationship("Warning", foreign_keys="[Warning.user_id]", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} tg_id={self.telegram_user_id} username={self.username}>"
