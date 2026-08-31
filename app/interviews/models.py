from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.applications.models import Application


class Interview(Base):
    """One interview per application."""

    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    scheduled_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meeting_link: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    application: Mapped["Application"] = relationship(back_populates="interview", lazy="selectin")
