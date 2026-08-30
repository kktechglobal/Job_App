"""Saved payment method for a candidate.

NEVER add card_number or cvv to this table. Storing a CVV after authorisation
is forbidden under PCI-DSS, and a raw card number puts the whole database in
audit scope. The card goes from the browser straight to the payment provider,
which returns the refs below; last4 and brand exist only to render
"Visa ****4242".
"""

from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint, text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import CardBrand, PaymentProvider
from app.database.base import Base

if TYPE_CHECKING:
    from app.candidate_founding_profile.models import CandidateProfile


class CandidateCard(Base):
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

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    candidate: Mapped["CandidateProfile"] = relationship(lazy="selectin")
