"""Model registry. app/database/db.py imports this before create_all().

Defining a model class registers its table on Base.metadata, and create_all()
only creates what is registered -- so every new model must be added here.
"""

from app.application.models import Application
from app.candidate_card.models import CandidateCard
from app.candidate_founding_profile.models import CandidateProfile
from app.candidate_social_media.models import CandidateSocialLink
from app.company_contact.models import CompanyContact
from app.company_founding_info.models import CompanyFoundingInfo
from app.company_socialmedia.models import CompanySocialLink
from app.employer_card.models import EmployerCard
from app.employer_profile.models import EmployerProfile
from app.interview.models import Interview
from app.job_post.models import JobPost
from app.my_jobs_promote_job.models import JobPromotion
from app.setting_account.models import AccountSetting
from app.skills.models import Skill, candidate_skills, job_required_skills
from app.users.models import User

__all__ = [
    "AccountSetting", "Application", "CandidateCard", "CandidateProfile",
    "CandidateSocialLink", "CompanyContact", "CompanyFoundingInfo",
    "CompanySocialLink", "EmployerCard", "EmployerProfile", "Interview",
    "JobPost", "JobPromotion", "Skill", "User",
    "candidate_skills", "job_required_skills",
]
