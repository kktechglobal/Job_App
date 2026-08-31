"""How well a candidate fits a job.

There are no models here on purpose: matching derives from skills that
candidates and jobs already own, and storing a derived score anywhere but the
application row would just be a cache to invalidate.
"""

from typing import Iterable, Sequence

from app.matching.schemas import MatchBreakdown


def _names(skills: Iterable) -> set:
    """Accepts Skill rows or plain strings, and normalises either.

    The Skill table is unique on a lowercased name, but a caller holding raw
    strings should not have to know that.
    """
    out = set()
    for skill in skills or []:
        name = getattr(skill, "name", skill)
        if name:
            out.add(str(name).strip().lower())
    return out


def breakdown(candidate_skills: Sequence, required_skills: Sequence) -> MatchBreakdown:
    required = _names(required_skills)
    held = _names(candidate_skills)

    if not required:
        # A job that asks for nothing is matched by everyone. Returning 0
        # here would rank open-requirement jobs last, which is backwards.
        return MatchBreakdown(score=100.0, matched=[], missing=[], required_total=0)

    matched = required & held
    # Denominator is what the job asks for, not what the candidate has --
    # otherwise holding one irrelevant extra skill would dilute a perfect
    # match.
    score = round(len(matched) / len(required) * 100, 2)

    return MatchBreakdown(
        score=score,
        matched=sorted(matched),
        missing=sorted(required - held),
        required_total=len(required),
    )


def score(candidate_skills: Sequence, required_skills: Sequence) -> float:
    """Just the number, for the application row's match_score column."""
    return breakdown(candidate_skills, required_skills).score
