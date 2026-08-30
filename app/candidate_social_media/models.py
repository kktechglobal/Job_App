from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import SocialPlatform
from app.database.base import Base

if TYPE_CHECKING:
    from app.candidate_founding_profile.models import CandidateProfile


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

    candidate: Mapped["CandidateProfile"] = relationship(lazy="selectin")
