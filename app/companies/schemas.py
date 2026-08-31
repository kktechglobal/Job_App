"""Request/response shapes for employers: the company, its satellites, and saved payment methods."""

from typing import List, Optional
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.companies.enums import IndustryType, OrganizationType, TeamSize
from app.global_enums import SocialPlatform
from app.global_enums import CardBrand, PaymentProvider
from app.jobs.enums import SubscriptionPlan


class EmployerProfileCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    company_description: Optional[str] = None
    about: Optional[str] = None
    banner_image_url: Optional[str] = Field(default=None, max_length=500)
    logo_url: Optional[str] = Field(default=None, max_length=500)


class EmployerProfileUpdate(BaseModel):
    company_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    company_description: Optional[str] = None
    about: Optional[str] = None
    banner_image_url: Optional[str] = Field(default=None, max_length=500)
    logo_url: Optional[str] = Field(default=None, max_length=500)


class EmployerProfileResponse(BaseModel):
    """The owner's view. Includes billing and trust state, read-only."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    company_name: str
    company_description: Optional[str]
    about: Optional[str]
    banner_image_url: Optional[str]
    logo_url: Optional[str]
    is_verified: bool
    subscription_plan: SubscriptionPlan


# ------------------------------------------------------------ founding info

class FoundingInfoUpsert(BaseModel):
    organization_type: Optional[OrganizationType] = None
    industry_type: Optional[IndustryType] = None
    # Mirrors ck_founding_year_sane on the table.
    year_of_establishment: Optional[int] = Field(default=None, ge=1800, le=2200)
    team_size: Optional[TeamSize] = None
    company_website: Optional[HttpUrl] = Field(default=None, max_length=500)
    company_vision: Optional[str] = None


class FoundingInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employer_id: int
    organization_type: Optional[OrganizationType]
    industry_type: Optional[IndustryType]
    year_of_establishment: Optional[int]
    team_size: Optional[TeamSize]
    company_website: Optional[str]
    company_vision: Optional[str]


# ----------------------------------------------------------------- contact

class CompanyContactUpsert(BaseModel):
    address: Optional[str] = Field(default=None, max_length=300)
    phone_number: Optional[str] = Field(default=None, max_length=30)
    # The company's public address (careers@...), not the owner's login email.
    email: Optional[EmailStr] = Field(default=None, max_length=320)


class CompanyContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employer_id: int
    address: Optional[str]
    phone_number: Optional[str]
    email: Optional[str]


# ------------------------------------------------------------ social links

class CompanySocialLinkCreate(BaseModel):
    platform: SocialPlatform
    url: HttpUrl = Field(..., max_length=500)


class CompanySocialLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: SocialPlatform
    url: str


# ------------------------------------------------------- the composite read

class PublicCompanyResponse(BaseModel):
    """One read for the whole company page, so a client needs one call.

    Built from an explicit field list, not by subtracting keys from a dict --
    a new column is invisible here until someone deliberately adds it.
    `user_id` and `subscription_plan` are not on it.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_name: str
    company_description: Optional[str]
    about: Optional[str]
    banner_image_url: Optional[str]
    logo_url: Optional[str]
    is_verified: bool
    founding_info: Optional[FoundingInfoResponse]
    contact: Optional[CompanyContactResponse]
    social_links: List[CompanySocialLinkResponse] = Field(default_factory=list)


class EmployerCardCreate(BaseModel):
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
    exp_year: int = Field(..., ge=2000, le=2100)
    cardholder_name: Optional[str] = Field(default=None, max_length=200)
    is_default: bool = False

    @model_validator(mode="after")
    def _check_expiry(self) -> "EmployerCardCreate":
        today = date.today()
        if (self.exp_year, self.exp_month) < (today.year, today.month):
            raise ValueError("card has already expired")
        return self


class EmployerCardUpdate(BaseModel):
    cardholder_name: Optional[str] = Field(default=None, max_length=200)
    exp_month: Optional[int] = Field(default=None, ge=1, le=12)
    exp_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    is_default: Optional[bool] = None


class EmployerCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employer_id: int
    provider: PaymentProvider
    brand: CardBrand
    last4: str
    exp_month: int
    exp_year: int
    cardholder_name: Optional[str]
    is_default: bool
    created_at: datetime
    updated_at: datetime
