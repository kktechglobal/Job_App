"""Request/response shapes for job seekers: the profile, its social links, and saved payment methods."""

from typing import List, Optional
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.global_enums import SocialPlatform
from app.global_enums import CardBrand, PaymentProvider


class CandidateProfileCreate(BaseModel):
    headline: Optional[str] = Field(default=None, max_length=200)
    bio: Optional[str] = None
    resume_url: Optional[str] = Field(default=None, max_length=500)
    years_experience: int = Field(default=0, ge=0, le=70)
    phone_number: Optional[str] = Field(default=None, max_length=30)
    country: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    skills: List[str] = Field(default_factory=list, max_length=50)

    @field_validator("skills")
    @classmethod
    def _normalise(cls, values: List[str]) -> List[str]:
        # The Skill table is unique on name, so "Python" and "python" would
        # otherwise become two rows and matching would quietly stop working.
        cleaned = [v.strip().lower() for v in values if v and v.strip()]
        return list(dict.fromkeys(cleaned))


class CandidateProfileUpdate(BaseModel):
    """Only the supplied fields change. Omit `skills` to leave them alone."""

    headline: Optional[str] = Field(default=None, max_length=200)
    bio: Optional[str] = None
    resume_url: Optional[str] = Field(default=None, max_length=500)
    years_experience: Optional[int] = Field(default=None, ge=0, le=70)
    phone_number: Optional[str] = Field(default=None, max_length=30)
    country: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    skills: Optional[List[str]] = Field(default=None, max_length=50)

    @field_validator("skills")
    @classmethod
    def _normalise(cls, values: Optional[List[str]]) -> Optional[List[str]]:
        if values is None:
            return None
        cleaned = [v.strip().lower() for v in values if v and v.strip()]
        return list(dict.fromkeys(cleaned))


class SocialLinkCreate(BaseModel):
    platform: SocialPlatform
    # HttpUrl so a malformed link is a 422, not a bad row. The service casts
    # it to str for the String(500) column.
    url: HttpUrl = Field(..., max_length=500)


class SocialLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: SocialPlatform
    url: str


class CandidateProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    headline: Optional[str]
    bio: Optional[str]
    resume_url: Optional[str]
    years_experience: int
    phone_number: Optional[str]
    country: Optional[str]
    city: Optional[str]
    skills: List[str] = Field(default_factory=list)

    @field_validator("skills", mode="before")
    @classmethod
    def _skill_names(cls, value):
        # Arrives as a list of Skill rows when read off the ORM object.
        return [s.name if hasattr(s, "name") else s for s in value or []]


def _reject_expired(exp_year: int, exp_month: int) -> None:
    today = date.today()
    if (exp_year, exp_month) < (today.year, today.month):
        raise ValueError("card has already expired")


class CandidateCardCreate(BaseModel):
    provider: PaymentProvider = Field(
        ..., description="Who holds the card: paystack, flutterwave or stripe"
    )
    customer_ref: str = Field(
        ..., min_length=1, max_length=120, description="The provider's customer id"
    )
    payment_method_ref: str = Field(
        ..., min_length=1, max_length=120,
        description="The provider's tokenised payment-method id",
    )
    brand: CardBrand = Field(
        default=CardBrand.OTHER, description="Card network, for display only"
    )
    last4: str = Field(..., pattern=r"^\d{4}$", description="Display digits, e.g. 4242")
    exp_month: int = Field(..., ge=1, le=12)
    # No hardcoded floor year: the validator below compares against today, so
    # this keeps working next year without anyone editing it.
    exp_year: int = Field(..., ge=2000, le=2100)
    cardholder_name: Optional[str] = Field(default=None, max_length=200)
    is_default: bool = False

    @model_validator(mode="after")
    def _check_expiry(self) -> "CandidateCardCreate":
        _reject_expired(self.exp_year, self.exp_month)
        return self


class CandidateCardUpdate(BaseModel):
    """Everything here is optional; only the supplied fields change.

    The provider refs are absent on purpose -- pointing a saved card at a
    different token is a new card, not an edit. Expiry is editable because
    providers reissue cards, but both halves are validated together in the
    service, against the values already stored.
    """

    cardholder_name: Optional[str] = Field(default=None, max_length=200)
    exp_month: Optional[int] = Field(default=None, ge=1, le=12)
    exp_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    is_default: Optional[bool] = None


class CandidateCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    provider: PaymentProvider
    brand: CardBrand
    last4: str
    exp_month: int
    exp_year: int
    cardholder_name: Optional[str]
    is_default: bool
    created_at: datetime
    updated_at: datetime
