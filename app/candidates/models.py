"""Everything that belongs to a job seeker.

Three tables that used to live in three packages -- candidate_profile,
candidate_card and candidate_social_media -- and were only ever used together.

The card docstring is worth keeping in front of you: NEVER add card_number or
cvv to CandidateCard. Storing a CVV after authorisation is forbidden under
PCI-DSS, and a raw card number puts the whole database in audit scope. The
card goes from the browser straight to the payment provider, which returns the
refs below; last4 and brand exist only to render "Visa ****4242".
"""

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.global_enums import CardBrand, PaymentProvider, SocialPlatform
from app.skills.models import candidate_skills

if TYPE_CHECKING:
    from app.applications.models import Application
    from app.skills.models import Skill
    from app.users.models import User


class CandidateProfile(Base):
    """A job seeker. One per CANDIDATE user."""

    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    headline: Mapped[Optional[str]] = mapped_column(String(200))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    resume_url: Mapped[Optional[str]] = mapped_column(String(500))
    years_experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    phone_number: Mapped[Optional[str]] = mapped_column(String(30))
    country: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    user: Mapped["User"] = relationship(back_populates="profile", lazy="selectin")
    applications: Mapped[List["Application"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    skills: Mapped[List["Skill"]] = relationship(
        secondary=candidate_skills, back_populates="candidates", lazy="selectin"
    )
    cards: Mapped[List["CandidateCard"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    social_links: Mapped[List["CandidateSocialLink"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )


class CandidateCard(Base):
    """A saved payment method. See the module docstring before adding columns."""

    __tablename__ = "candidate_cards"

    __table_args__ = (
        UniqueConstraint("provider", "payment_method_ref", name="uq_candidate_cards_provider_ref"),
        CheckConstraint("exp_month BETWEEN 1 AND 12", name="ck_candidate_cards_exp_month"),
        CheckConstraint("length(last4) = 4", name="ck_candidate_cards_last4"),
        # Partial index: unique only among rows where is_default is true, so a
        # person may save many cards but only one default.
        Index(
            "uq_candidate_cards_one_default", "candidate_id", unique=True,
            postgresql_where=text("is_default"), sqlite_where=text("is_default"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True, nullable=False
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

    candidate: Mapped["CandidateProfile"] = relationship(back_populates="cards", lazy="selectin")


class CandidateSocialLink(Base):
    """One row per platform per candidate."""

    __tablename__ = "candidate_social_links"

    __table_args__ = (
        UniqueConstraint("candidate_id", "platform", name="uq_candidate_social_platform"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    platform: Mapped[SocialPlatform] = mapped_column(
        SAEnum(SocialPlatform, name="social_platform", native_enum=False, length=20), nullable=False
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    candidate: Mapped["CandidateProfile"] = relationship(
        back_populates="social_links", lazy="selectin"
    )
