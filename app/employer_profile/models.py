from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.job_post.enums import SubscriptionPlan

if TYPE_CHECKING:
    from app.job_post.models import JobPost
    from app.users.models import User


class EmployerProfile(Base):
    """A company. One per EMPLOYER user."""

    __tablename__ = "employer_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    company_description: Mapped[Optional[str]] = mapped_column(Text)
    about: Mapped[Optional[str]] = mapped_column(Text)

    banner_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    subscription_plan: Mapped[SubscriptionPlan] = mapped_column(
        SAEnum(SubscriptionPlan, name="subscription_plan", native_enum=False, length=20),
        default=SubscriptionPlan.FREE, nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="employer_profile", lazy="selectin")
    jobs: Mapped[List["JobPost"]] = relationship(
        back_populates="employer", cascade="all, delete-orphan", passive_deletes=True
    )
