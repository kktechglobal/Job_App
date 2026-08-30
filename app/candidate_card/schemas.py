from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

# --- Saved Candidate Payment Card Schemas ---

class SavedCandidateCardCreate(BaseModel):
    card_holder_name: str = Field(..., min_length=2)
    brand: str = Field(..., example="Visa")
    last_four: str = Field(..., min_length=4, max_length=4, pattern=r"^\d{4}$")
    exp_month: int = Field(..., ge=1, le=12)
    exp_year: int = Field(..., ge=2026, le=2050)
    payment_token: str = Field(..., min_length=5, description="Tokenized reference from payment gateway")
    is_default: Optional[bool] = False

class SavedCandidateCardUpdate(BaseModel):
    card_holder_name: Optional[str] = None
    exp_month: Optional[int] = Field(None, ge=1, le=12)
    exp_year: Optional[int] = Field(None, ge=2026, le=2050)
    is_default: Optional[bool] = None

class SavedCandidateCardResponse(BaseModel):
    id: int
    candidate_id: int
    card_holder_name: str
    brand: str
    last_four: str
    exp_month: int
    exp_year: int
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True