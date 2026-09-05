"""Auto Delete Queue model."""
from datetime import datetime, timezone
from sqlalchemy import Integer, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.session import Base


class AutoDeleteQueue(Base):
    __tablename__ = "auto_delete_queue"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    delete_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Relationships
    group = relationship("Group")

    def __repr__(self) -> str:
        return f"<AutoDeleteQueue group_id={self.group_id} message_id={self.message_id} delete_at={self.delete_at}>"
