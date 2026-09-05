"""Group model."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import BigInteger, String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_group_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    group_name: Mapped[str] = mapped_column(String(255), default="")
    rules: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    settings = relationship("GroupSettings", back_populates="group", uselist=False, cascade="all, delete-orphan")
    invite_links = relationship("ReferralInviteLink", back_populates="group", cascade="all, delete-orphan")
    requirements = relationship("ReferralRequirement", back_populates="group", cascade="all, delete-orphan")
    warnings = relationship("Warning", back_populates="group", cascade="all, delete-orphan")
    locks = relationship("GroupLock", back_populates="group", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Group id={self.id} tg_group_id={self.telegram_group_id} name={self.group_name}>"
