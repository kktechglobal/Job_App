from typing import Optional, TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.company_founding_info.enums import IndustryType, OrganizationType, TeamSize
from app.database.base import Base

if TYPE_CHECKING:
    from app.employer_profile.models import EmployerProfile


class CompanyFoundingInfo(Base):
    """Registration details. One per company."""

    __tablename__ = "company_founding_info"

    __table_args__ = (
        CheckConstraint(
            "year_of_establishment IS NULL OR year_of_establishment BETWEEN 1800 AND 2200",
            name="ck_founding_year_sane",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employer_id: Mapped[int] = mapped_column(
        ForeignKey("employer_profiles.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    organization_type: Mapped[Optional[OrganizationType]] = mapped_column(
        SAEnum(OrganizationType, name="organization_type", native_enum=False, length=30)
    )
    industry_type: Mapped[Optional[IndustryType]] = mapped_column(
        SAEnum(IndustryType, name="industry_type", native_enum=False, length=30), index=True
    )
    year_of_establishment: Mapped[Optional[int]] = mapped_column(Integer)
    team_size: Mapped[Optional[TeamSize]] = mapped_column(
        SAEnum(TeamSize, name="team_size", native_enum=False, length=10)
    )

    company_website: Mapped[Optional[str]] = mapped_column(String(500))
    company_vision: Mapped[Optional[str]] = mapped_column(Text)

    employer: Mapped["EmployerProfile"] = relationship(lazy="selectin")
