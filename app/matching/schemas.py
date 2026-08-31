"""Shapes for the candidate/job match score."""

from typing import List

from pydantic import BaseModel, Field


class MatchBreakdown(BaseModel):
    """Why a score is what it is.

    A bare number is not actionable -- a candidate told "62%" learns nothing,
    while one told "you have 5 of 8 required skills; missing: kubernetes,
    terraform, go" knows what to do next.
    """

    score: float = Field(..., ge=0, le=100)
    matched: List[str] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)
    required_total: int
