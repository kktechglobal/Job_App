from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import SocialPlatform
from app.database.base import Base

if TYPE_CHECKING:
    from app.employer_profile.models import EmployerProfile


class CompanySocialLink(Base):
    """One row per platform per company."""

    __tablename__ = "company_social_links"

    __table_args__ = (
        UniqueConstraint("employer_id", "platform", name="uq_company_social_platform"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employer_id: Mapped[int] = mapped_column(
        ForeignKey("employer_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    platform: Mapped[SocialPlatform] = mapped_column(
        SAEnum(SocialPlatform, name="social_platform", native_enum=False, length=20), nullable=False
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    employer: Mapped["EmployerProfile"] = relationship(lazy="selectin")
