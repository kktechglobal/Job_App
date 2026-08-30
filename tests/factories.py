from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app import models as m
from app.job_post.enums import ExperienceLevel, JobLevel, JobType, SalaryType
from app.users.enums import UserRole


def make_user(email="dev@mail.com", role=UserRole.CANDIDATE, name="Ken Dev"):
    return m.User(email=email, hashed_password="x" * 60, full_name=name, role=role)


def make_job(employer_id, *, salary_min="100000.00", salary_max="200000.00", **kw):
    defaults = dict(
        employer_id=employer_id,
        title="Backend Developer",
        job_role="engineer",
        job_description="Build and maintain the API.",
        salary_min=Decimal(salary_min),
        salary_max=Decimal(salary_max),
        salary_type=SalaryType.MONTHLY,
        job_level=JobLevel.MID,
        experience_level=ExperienceLevel.THREE_TO_FIVE_YEARS,
        job_type=JobType.FULL_TIME,
        vacancies=2,
        expiration_date=datetime.now(timezone.utc) + timedelta(days=30),
        country="NG",
        city="Lagos",
        job_benefits=["remote", "health insurance"],
    )
    defaults.update(kw)
    return m.JobPost(**defaults)
