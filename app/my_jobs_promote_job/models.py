from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.job_post.enums import Currency
from app.my_jobs_promote_job.enums import PromotionPlan

if TYPE_CHECKING:
    from app.job_post.models import JobPost


class JobPromotion(Base):
    """A paid promotion for one job."""

    __tablename__ = "job_promotions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job_posts.id", ondelete="CASCADE"), index=True, nullable=False
    )

    plan: Mapped[PromotionPlan] = mapped_column(
        SAEnum(PromotionPlan, name="promotion_plan", native_enum=False, length=20), nullable=False
    )
    # Ask `featured_until > now()` rather than storing a flag -- a date expires
    # on its own, a boolean waits for someone to remember to unset it.
    featured_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        SAEnum(Currency, name="currency", native_enum=False, length=3),
        default=Currency.NGN, nullable=False,
    )
    payment_reference: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["JobPost"] = relationship(lazy="selectin")
