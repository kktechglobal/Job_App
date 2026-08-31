"""Each test names a mistake the models used to make. A failure means it is back."""

import pytest
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app import models as m
from app.applications.enums import ApplicationStatus
from app.global_enums import CardBrand, PaymentProvider, SocialPlatform
from app.users.enums import UserRole
from tests.factories import make_job, make_user


async def seed(session):
    """A candidate, an employer with a profile, and one open job.

    Uses `user=seeker`, not `user_id=seeker.id` -- assigning the relationship
    populates both sides in memory; assigning the FK does not.
    """
    seeker, boss = make_user(), make_user("hr@acme.com", UserRole.EMPLOYER, "Ada Boss")
    cp = m.CandidateProfile(user=seeker, headline="Python dev", years_experience=4)
    ep = m.EmployerProfile(user=boss, company_name="Acme")
    session.add_all([seeker, boss, cp, ep])
    await session.flush()
    job = make_job(ep.id)
    session.add(job)
    await session.commit()
    return seeker, boss, cp, ep, job


# --------------------------------------------------------------- basics
async def test_bcrypt_hash_fits(session):
    """hashed_password was String(50); a bcrypt hash is 60 chars and was truncated."""
    u = make_user()
    u.hashed_password = "$2b$12$" + "a" * 53  # 60 chars, like real bcrypt
    session.add(u)
    await session.commit()
    stored = (await session.execute(select(m.User.hashed_password))).scalar_one()
    assert len(stored) == 60


async def test_new_user_can_log_in(session):
    """is_active used to default to False, so every account was born locked out."""
    u = make_user()
    session.add(u)
    await session.commit()
    assert u.is_active is True
    assert u.is_email_verified is False
    assert u.role is UserRole.CANDIDATE          # role defaults, and is a real enum


async def test_email_is_unique(session):
    session.add(make_user("dup@mail.com"))
    await session.commit()
    session.add(make_user("dup@mail.com"))
    with pytest.raises(IntegrityError):
        await session.commit()


# --------------------------------------------------- constraints in the DB
async def test_salary_range_is_enforced(session):
    _, _, _, ep, _ = await seed(session)
    session.add(make_job(ep.id, salary_min="900000.00", salary_max="100000.00"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_cannot_apply_to_same_job_twice(session):
    _, _, cp, _, job = await seed(session)
    session.add(m.Application(job_id=job.id, candidate_id=cp.id))
    await session.commit()
    session.add(m.Application(job_id=job.id, candidate_id=cp.id))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_money_is_exact_not_float(session):
    """Float would have made this 0.30000000000000004-style wrong."""
    _, _, _, ep, _ = await seed(session)
    job = make_job(ep.id, salary_min="0.10", salary_max="0.20")
    session.add(job)
    await session.commit()
    assert job.salary_min + job.salary_max == Decimal("0.30")


# ------------------------------------------------------- async relationships
async def test_relationships_load_without_missinggreenlet(session):
    """Touching a relationship in async code used to raise MissingGreenlet."""
    _, _, cp, _, job = await seed(session)
    session.add(m.Application(job_id=job.id, candidate_id=cp.id))
    await session.commit()
    session.expunge_all()

    app_row = (await session.execute(select(m.Application))).scalars().first()
    assert app_row.job.title == "Backend Developer"
    assert app_row.candidate.user.full_name == "Ken Dev"
    assert app_row.job.employer.company_name == "Acme"
    assert app_row.status is ApplicationStatus.SUBMITTED


async def test_back_populates_both_directions(session):
    _, boss, _, ep, job = await seed(session)

    assert job.employer.company_name == "Acme"
    assert ep.user.id == boss.id
    assert boss.employer_profile.id == ep.id

    loaded = (await session.execute(
        select(m.EmployerProfile).options(selectinload(m.EmployerProfile.jobs))
    )).scalars().first()
    assert [j.title for j in loaded.jobs] == ["Backend Developer"]


# ------------------------------------------------------------- cascades
async def test_deleting_user_removes_their_data(session):
    seeker, _, cp, _, job = await seed(session)
    session.add(m.Application(job_id=job.id, candidate_id=cp.id))
    await session.commit()

    await session.delete(seeker)
    await session.commit()

    assert (await session.execute(select(m.CandidateProfile))).scalars().all() == []
    assert (await session.execute(select(m.Application))).scalars().all() == []


async def test_deleting_job_removes_its_applications(session):
    _, _, cp, _, job = await seed(session)
    session.add(m.Application(job_id=job.id, candidate_id=cp.id))
    await session.commit()
    await session.delete(job)
    await session.commit()
    assert (await session.execute(select(m.Application))).scalars().all() == []


# ------------------------------------------------------ skills many-to-many
async def test_skills_are_shared_rows_not_text(session):
    """The whole point: a candidate's "python" and a job's "python" are ONE row."""
    _, _, cp, ep, job = await seed(session)
    python = m.Skill(name="python")
    sql = m.Skill(name="sql")
    rust = m.Skill(name="rust")
    session.add_all([python, sql, rust])
    await session.flush()

    cp = (await session.execute(
        select(m.CandidateProfile).where(m.CandidateProfile.id == cp.id)
        .options(selectinload(m.CandidateProfile.skills))
    )).scalars().one()
    job = (await session.execute(
        select(m.JobPost).where(m.JobPost.id == job.id)
        .options(selectinload(m.JobPost.required_skills))
    )).scalars().one()

    cp.skills = [python, sql]
    job.required_skills = [python, rust]
    await session.commit()

    overlap = {s.id for s in cp.skills} & {s.id for s in job.required_skills}
    assert overlap == {python.id}

    loaded = (await session.execute(
        select(m.Skill).where(m.Skill.name == "python").options(
            selectinload(m.Skill.candidates), selectinload(m.Skill.jobs)
        )
    )).scalars().one()
    assert len(loaded.candidates) == 1 and len(loaded.jobs) == 1


async def test_skill_names_are_unique(session):
    session.add_all([m.Skill(name="python"), m.Skill(name="python")])
    with pytest.raises(IntegrityError):
        await session.commit()


# --------------------------------------------------------- social links
async def test_one_link_per_platform(session):
    _, _, cp, _, _ = await seed(session)
    session.add(m.CandidateSocialLink(
        candidate_id=cp.id, platform=SocialPlatform.LINKEDIN, url="https://linkedin.com/in/ken"))
    await session.commit()
    session.add(m.CandidateSocialLink(
        candidate_id=cp.id, platform=SocialPlatform.LINKEDIN, url="https://linkedin.com/in/other"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_adding_a_new_platform_needs_no_migration(session):
    """Five fixed url columns made TikTok a schema change. Now it is a row."""
    _, _, cp, _, _ = await seed(session)
    session.add_all([
        m.CandidateSocialLink(candidate_id=cp.id, platform=p, url=f"https://{p.value}.com/ken")
        for p in (SocialPlatform.TIKTOK, SocialPlatform.GITHUB, SocialPlatform.FACEBOOK)
    ])
    await session.commit()
    links = (await session.execute(select(m.CandidateSocialLink))).scalars().all()
    assert len(links) == 3


# ------------------------------------------------------------- payments
async def test_card_stores_a_token_not_a_card(session):
    _, _, cp, _, _ = await seed(session)
    card = m.CandidateCard(
        candidate_id=cp.id, provider=PaymentProvider.PAYSTACK,
        customer_ref="CUS_abc123", payment_method_ref="AUTH_xyz789",
        brand=CardBrand.VISA, last4="4242", exp_month=12, exp_year=2030)
    session.add(card)
    await session.commit()

    columns = {c.name for c in m.CandidateCard.__table__.columns}
    assert "cvv" not in columns, "storing a CVV violates PCI-DSS"
    assert "card_number" not in columns, "storing a raw PAN is never allowed"
    assert card.last4 == "4242"


async def test_impossible_expiry_month_rejected(session):
    _, _, cp, _, _ = await seed(session)
    session.add(m.CandidateCard(
        candidate_id=cp.id, provider=PaymentProvider.PAYSTACK,
        customer_ref="CUS_1", payment_method_ref="AUTH_1",
        brand=CardBrand.VISA, last4="4242", exp_month=13, exp_year=2030))
    with pytest.raises(IntegrityError):
        await session.commit()


# ------------------------------------------------------------ promotions
async def test_promotion_knows_which_job(session):
    """The old table had no job_id at all -- it could not say what was promoted."""
    from datetime import datetime, timedelta, timezone
    from app.jobs.enums import PromotionPlan

    _, _, _, _, job = await seed(session)
    promo = m.JobPromotion(
        job_id=job.id, plan=PromotionPlan.FEATURED,
        featured_until=datetime.now(timezone.utc) + timedelta(days=7),
        amount_paid=Decimal("15000.00"), payment_reference="PSK_REF_001")
    session.add(promo)
    await session.commit()
    assert promo.job.title == "Backend Developer"
    assert promo.amount_paid == Decimal("15000.00")


# ------------------------------------------------- the columns that had to go
@pytest.mark.parametrize("model, gone", [
    (m.Application, ["newest", "oldest", "filter_applications", "sort_applications",
                     "edit_job_application", "delete_job_application", "notification_id"]),
    (m.AccountSetting, ["change_password", "current_password", "new_password"]),
    (m.EmployerProfile, ["save_and_next"]),
])
def test_button_columns_are_gone(model, gone):
    columns = {c.name for c in model.__table__.columns}
    assert columns.isdisjoint(gone), f"{sorted(columns & set(gone))} should not be columns"


def test_candidate_profile_has_no_company_columns():
    """Six company fields had been copy-pasted onto the candidate."""
    columns = {c.name for c in m.CandidateProfile.__table__.columns}
    company_only = {"organization_type", "year_of_establishment", "industry_type",
                    "team_size", "company_website", "company_vision"}
    assert columns.isdisjoint(company_only)
    assert {"headline", "resume_url", "years_experience"} <= columns


# ------------------------------------------- second-pass audit fixes
async def test_only_one_default_card_per_person(session):
    _, _, cp, _, _ = await seed(session)
    def card(ref, default):
        return m.CandidateCard(
            candidate_id=cp.id, provider=PaymentProvider.PAYSTACK,
            customer_ref="CUS_1", payment_method_ref=ref,
            brand=CardBrand.VISA, last4="4242", exp_month=6, exp_year=2030,
            is_default=default)
    session.add_all([card("AUTH_1", True), card("AUTH_2", False)])
    await session.commit()                       # one default, one not

    session.add(card("AUTH_3", True))            # a second default
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_match_score_must_be_a_percentage(session):
    _, _, cp, _, job = await seed(session)
    session.add(m.Application(job_id=job.id, candidate_id=cp.id, match_score=140.0))
    with pytest.raises(IntegrityError):
        await session.commit()


def test_subscription_plan_belongs_to_the_company_not_the_job():
    """It was on JobPost, so forty jobs could disagree about one company's plan."""
    assert "subscription_plan" in {c.name for c in m.EmployerProfile.__table__.columns}
    assert "subscription_plan" not in {c.name for c in m.JobPost.__table__.columns}


def test_one_fact_is_stored_in_one_place():
    """No column may describe the same thing in two tables."""
    candidate = {c.name for c in m.CandidateProfile.__table__.columns}
    settings = {c.name for c in m.AccountSetting.__table__.columns}
    assert candidate & settings == {"id", "user_id"}, "a person's details live in ONE table"

    for model in (m.CandidateProfile, m.JobPost):
        columns = {c.name for c in model.__table__.columns}
        assert not ("location" in columns and "city" in columns), \
            f"{model.__name__}: `location` repeats what city/country already say"
