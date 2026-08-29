from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.users.models import User


class AccountSetting(Base):
    """Notification and privacy preferences. One per user."""

    __tablename__ = "account_information"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    job_alert_emails: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    profile_is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(lazy="selectin")
