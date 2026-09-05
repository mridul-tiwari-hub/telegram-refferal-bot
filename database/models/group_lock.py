"""Group Locks model."""
from sqlalchemy import Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class GroupLock(Base):
    __tablename__ = "group_locks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), unique=True, nullable=False)
    lock_all: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_text: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_photos: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_videos: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_stickers: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_gifs: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_voice: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_links: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_polls: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    group = relationship("Group", back_populates="locks")

    def __repr__(self) -> str:
        return f"<GroupLock group_id={self.group_id} lock_all={self.lock_all}>"
