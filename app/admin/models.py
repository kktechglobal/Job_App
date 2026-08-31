"""The administrator audit trail.

Administrators act on other people's accounts and other companies' job posts.
Those actions need to be attributable and reviewable afterwards, so every one
of them writes a row here.

`target_id` is deliberately a plain integer rather than a foreign key. A real
FK would need an ON DELETE rule, and every useful choice is wrong: CASCADE
erases the audit record at exactly the moment it matters, and RESTRICT means
an audited row can never be deleted. The log outlives what it describes.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.admin.enums import AdminAction, AdminTarget
from app.database.base import Base

if TYPE_CHECKING:
    from app.users.models import User


class AdminActionLog(Base):
    __tablename__ = "admin_action_logs"

    __table_args__ = (
        # The two questions this table gets asked: "what happened to this
        # thing?" and "what has this administrator been doing?"
        Index("ix_admin_logs_target", "target_type", "target_id"),
        Index("ix_admin_logs_admin_time", "admin_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # RESTRICT, not CASCADE: deleting an administrator must not quietly delete
    # the record of what they did.
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    action: Mapped[AdminAction] = mapped_column(
        SAEnum(AdminAction, name="admin_action", native_enum=False, length=30), nullable=False
    )
    target_type: Mapped[AdminTarget] = mapped_column(
        SAEnum(AdminTarget, name="admin_target", native_enum=False, length=20), nullable=False
    )
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Free text for context a column cannot carry -- why a job was rejected,
    # which support ticket prompted a deactivation.
    note: Mapped[Optional[str]] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    admin: Mapped["User"] = relationship(lazy="selectin")
