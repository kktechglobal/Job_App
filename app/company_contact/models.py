from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.employer_profile.models import EmployerProfile


class CompanyContact(Base):
    """Public contact details. One per company."""

    __tablename__ = "company_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employer_id: Mapped[int] = mapped_column(
        ForeignKey("employer_profiles.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    address: Mapped[Optional[str]] = mapped_column(String(300))
    phone_number: Mapped[Optional[str]] = mapped_column(String(30))
    # The company's public address (careers@...), not the owner's login email.
    email: Mapped[Optional[str]] = mapped_column(String(320))

    employer: Mapped["EmployerProfile"] = relationship(lazy="selectin")
