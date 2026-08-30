from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl


SocialPlatform = Literal["facebook", "linkedin", "instagram", "website"]
JobType = Literal["full_time", "part_time", "contract", "internship", "remote"]






class SavedCardCreate(BaseModel):
    provider: Literal["visa", "mastercard", "verve", "amex"]
    last4: str
    expiry_month: int
    expiry_year: int
    holder_name: str