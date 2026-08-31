"""Model registry. app/database/db.py imports this before create_all().

Defining a model class registers its table on Base.metadata, and create_all()
only creates what is registered -- so every new model must be added here.
"""

from app.admin.models import AdminActionLog
from app.applications.models import Application
from app.auth.models import PasswordResetToken, RefreshToken
from app.candidates.models import CandidateCard, CandidateProfile, CandidateSocialLink
from app.companies.models import (
    CompanyContact, CompanyFoundingInfo, CompanySocialLink, EmployerCard, EmployerProfile,
)
from app.interviews.models import Interview
from app.jobs.models import JobPost, JobPromotion
from app.notifications.models import Notification
from app.skills.models import Skill, candidate_skills, job_required_skills
from app.users.models import AccountSetting, User

__all__ = [
    "AccountSetting", "AdminActionLog", "Application", "CandidateCard",
    "PasswordResetToken", "RefreshToken",
    "CandidateProfile", "CandidateSocialLink", "CompanyContact",
    "CompanyFoundingInfo", "CompanySocialLink", "EmployerCard", "EmployerProfile",
    "Interview", "JobPost", "JobPromotion", "Notification", "Skill", "User",
    "candidate_skills", "job_required_skills",
]
