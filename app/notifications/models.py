"""Outbound messages.

Not wired into a router yet: nothing sends notifications until there is a
worker to deliver them (see app/workers/). The table exists first so the rest
of the app can record an intent to notify without knowing how it is delivered.

Rows are written by the domain that causes them -- an application status
change, an interview booking -- and drained by a worker. That indirection is
the point: an HTTP request should never wait on an email provider.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.notifications.enums import NotificationChannel, NotificationStatus

if TYPE_CHECKING:
    from app.users.models import User


class Notification(Base):
    __tablename__ = "notifications"

    __table_args__ = (
        # The worker's query: what is still waiting to go out, oldest first.
        Index("ix_notifications_pending", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    channel: Mapped[NotificationChannel] = mapped_column(
        SAEnum(NotificationChannel, name="notification_channel", native_enum=False, length=20),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[NotificationStatus] = mapped_column(
        SAEnum(NotificationStatus, name="notification_status", native_enum=False, length=20),
        default=NotificationStatus.PENDING, nullable=False, index=True,
    )
    # Kept so a failure can be diagnosed without reading the worker's logs.
    error: Mapped[Optional[str]] = mapped_column(String(500))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(lazy="selectin")
