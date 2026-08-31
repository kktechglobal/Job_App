"""Everything that belongs to an employer.

Five tables that used to live in five packages. The company is deliberately
not one wide table: EmployerProfile is the identity, and three 1:1 satellites
plus a link collection hold the rest. That decomposition is what lets a logo
change touch one row instead of four.

NEVER add card_number or cvv to EmployerCard -- see app/candidates/models.py
for the full reasoning; it applies identically here.
"""

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.companies.enums import IndustryType, OrganizationType, TeamSize
from app.database.base import Base
from app.global_enums import CardBrand, PaymentProvider, SocialPlatform
from app.jobs.enums import SubscriptionPlan

if TYPE_CHECKING:
    from app.jobs.models import JobPost
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
    cards: Mapped[List["EmployerCard"]] = relationship(
        back_populates="employer", cascade="all, delete-orphan", passive_deletes=True
    )

    # The company's details are split across three tables rather than widened
    # onto this one. Each is 1:1 except the links, so scalars load eagerly and
    # the collection is loaded per query.
    founding_info: Mapped[Optional["CompanyFoundingInfo"]] = relationship(
        back_populates="employer", lazy="selectin",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    contact: Mapped[Optional["CompanyContact"]] = relationship(
        back_populates="employer", lazy="selectin",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    social_links: Mapped[List["CompanySocialLink"]] = relationship(
        back_populates="employer", cascade="all, delete-orphan", passive_deletes=True
    )


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

    employer: Mapped["EmployerProfile"] = relationship(
        back_populates="founding_info", lazy="selectin"
    )


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

    employer: Mapped["EmployerProfile"] = relationship(
        back_populates="contact", lazy="selectin"
    )


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

    employer: Mapped["EmployerProfile"] = relationship(
        back_populates="social_links", lazy="selectin"
    )


class EmployerCard(Base):
    """A saved payment method. See the module docstring before adding columns."""

    __tablename__ = "employer_cards"

    __table_args__ = (
        UniqueConstraint("provider", "payment_method_ref", name="uq_employer_cards_provider_ref"),
        CheckConstraint("exp_month BETWEEN 1 AND 12", name="ck_employer_cards_exp_month"),
        CheckConstraint("length(last4) = 4", name="ck_employer_cards_last4"),
        Index(
            "uq_employer_cards_one_default", "employer_id", unique=True,
            postgresql_where=text("is_default"), sqlite_where=text("is_default"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employer_id: Mapped[int] = mapped_column(
        ForeignKey("employer_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )

    provider: Mapped[PaymentProvider] = mapped_column(
        SAEnum(PaymentProvider, name="payment_provider", native_enum=False, length=20),
        nullable=False,
    )
    customer_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    payment_method_ref: Mapped[str] = mapped_column(String(120), nullable=False)

    brand: Mapped[CardBrand] = mapped_column(
        SAEnum(CardBrand, name="card_brand", native_enum=False, length=20),
        default=CardBrand.OTHER, nullable=False,
    )
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    exp_month: Mapped[int] = mapped_column(Integer, nullable=False)
    exp_year: Mapped[int] = mapped_column(Integer, nullable=False)
    cardholder_name: Mapped[Optional[str]] = mapped_column(String(200))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    employer: Mapped["EmployerProfile"] = relationship(back_populates="cards", lazy="selectin")
