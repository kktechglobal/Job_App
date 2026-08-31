"""End-to-end tests for the candidate profile and the two card modules.

Authentication is stubbed by overriding get_current_user: users/routers.py is
still unfinished, so there is no /auth/login to mint a real token yet. The
role check inside require_role is NOT stubbed -- it runs against the user each
test installs, so the 403s below are the real ones.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from tests.conftest import make_engine

import app.models  # noqa: F401  -- registers every table on Base.metadata
from app.auth.dependencies import get_current_user
from app.database.base import Base
from app.database.db import get_session
from app.main import app
from app.users.models import User, UserRole


class _Caller:
    """Whoever the current test is acting as."""

    user: User | None = None


@pytest_asyncio.fixture
async def client():
    engine = make_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _session():
        async with maker() as session:
            yield session

    async def _current_user():
        return _Caller.user

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_user] = _current_user

    # Two candidates and one employer, so isolation can actually be tested.
    async with maker() as setup:
        users = {
            "candidate": User(
                email="c1@example.com", username="c1", hashed_password="x",
                full_name="C One", role=UserRole.CANDIDATE),
            "other": User(
                email="c2@example.com", username="c2", hashed_password="x",
                full_name="C Two", role=UserRole.CANDIDATE),
            "employer": User(
                email="e1@example.com", username="e1", hashed_password="x",
                full_name="E One", role=UserRole.EMPLOYER),
        }
        setup.add_all(list(users.values()))
        await setup.commit()
        for u in users.values():
            await setup.refresh(u)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.users = users
        ac.maker = maker
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


def act_as(client, who):
    _Caller.user = client.users[who]


CARD = {
    "provider": "paystack",
    "customer_ref": "CUS_1",
    "payment_method_ref": "AUTH_1",
    "brand": "visa",
    "last4": "4242",
    "exp_month": 6,
    "exp_year": 2030,
    "cardholder_name": "C One",
}


async def make_profile(client):
    act_as(client, "candidate")
    return await client.post(
        "/candidate-profile",
        json={"headline": "Python dev", "years_experience": 4, "skills": ["Python", "python", " FastAPI "]},
    )


# ------------------------------------------------------- candidate profile

async def test_profile_create_normalises_and_dedupes_skills(client):
    res = await make_profile(client)
    assert res.status_code == 201, res.text
    assert res.json()["skills"] == ["python", "fastapi"]


async def test_profile_cannot_be_created_twice(client):
    await make_profile(client)
    res = await client.post("/candidate-profile", json={"years_experience": 1})
    assert res.status_code == 409


async def test_profile_patch_only_touches_what_it_is_sent(client):
    await make_profile(client)
    res = await client.patch("/candidate-profile/me", json={"city": "Lagos"})
    assert res.status_code == 200
    body = res.json()
    assert body["city"] == "Lagos"
    assert body["headline"] == "Python dev"      # untouched
    assert body["skills"] == ["python", "fastapi"]


async def test_profile_404_before_it_exists(client):
    act_as(client, "candidate")
    assert (await client.get("/candidate-profile/me")).status_code == 404


async def test_employer_cannot_use_candidate_profile_routes(client):
    act_as(client, "employer")
    assert (await client.get("/candidate-profile/me")).status_code == 403


async def test_social_link_is_one_per_platform(client):
    await make_profile(client)
    link = {"platform": "linkedin", "url": "https://linkedin.com/in/one"}
    assert (await client.post("/candidate-profile/me/social-links", json=link)).status_code == 201
    assert (await client.post("/candidate-profile/me/social-links", json=link)).status_code == 409


async def test_social_link_rejects_a_bad_url(client):
    await make_profile(client)
    res = await client.post(
        "/candidate-profile/me/social-links", json={"platform": "github", "url": "not-a-url"}
    )
    assert res.status_code == 422


# ------------------------------------------------------------ card basics

async def test_first_card_becomes_the_default(client):
    await make_profile(client)
    res = await client.post("/candidate-payment-cards", json=CARD)
    assert res.status_code == 201, res.text
    assert res.json()["is_default"] is True


async def test_response_never_leaks_the_provider_refs(client):
    await make_profile(client)
    body = (await client.post("/candidate-payment-cards", json=CARD)).json()
    assert "customer_ref" not in body
    assert "payment_method_ref" not in body
    assert body["last4"] == "4242"


async def test_expired_card_is_rejected(client):
    await make_profile(client)
    res = await client.post("/candidate-payment-cards", json={**CARD, "exp_year": 2020})
    assert res.status_code == 422


async def test_saving_the_same_token_twice_is_a_conflict(client):
    await make_profile(client)
    await client.post("/candidate-payment-cards", json=CARD)
    res = await client.post("/candidate-payment-cards", json=CARD)
    assert res.status_code == 409


async def test_card_requires_a_profile_first(client):
    act_as(client, "candidate")
    res = await client.post("/candidate-payment-cards", json=CARD)
    assert res.status_code == 404


# ------------------------------------------------- the one-default invariant

async def test_switching_default_on_create_does_not_trip_the_unique_index(client):
    """This is the bug the old service had: the INSERT of the new default
    reached the database while the old default row was still true."""
    await make_profile(client)
    first = await client.post("/candidate-payment-cards", json=CARD)
    assert first.status_code == 201

    second = await client.post(
        "/candidate-payment-cards",
        json={**CARD, "payment_method_ref": "AUTH_2", "is_default": True},
    )
    assert second.status_code == 201, second.text
    assert second.json()["is_default"] is True

    listed = (await client.get("/candidate-payment-cards")).json()
    assert [c["is_default"] for c in listed].count(True) == 1


async def test_switching_default_on_patch_does_not_trip_the_unique_index(client):
    await make_profile(client)
    a = (await client.post("/candidate-payment-cards", json=CARD)).json()
    b = (await client.post(
        "/candidate-payment-cards", json={**CARD, "payment_method_ref": "AUTH_2"}
    )).json()

    res = await client.patch(f"/candidate-payment-cards/{b['id']}", json={"is_default": True})
    assert res.status_code == 200, res.text

    listed = (await client.get("/candidate-payment-cards")).json()
    defaults = [c["id"] for c in listed if c["is_default"]]
    assert defaults == [b["id"]]
    assert a["id"] not in defaults


async def test_default_cannot_be_unset_on_its_own(client):
    await make_profile(client)
    card = (await client.post("/candidate-payment-cards", json=CARD)).json()
    res = await client.patch(f"/candidate-payment-cards/{card['id']}", json={"is_default": False})
    assert res.status_code == 422


async def test_deleting_the_default_promotes_another_card(client):
    await make_profile(client)
    a = (await client.post("/candidate-payment-cards", json=CARD)).json()
    b = (await client.post(
        "/candidate-payment-cards", json={**CARD, "payment_method_ref": "AUTH_2"}
    )).json()
    assert a["is_default"] and not b["is_default"]

    assert (await client.delete(f"/candidate-payment-cards/{a['id']}")).status_code == 204

    listed = (await client.get("/candidate-payment-cards")).json()
    assert len(listed) == 1
    assert listed[0]["id"] == b["id"]
    assert listed[0]["is_default"] is True


async def test_patch_rejects_an_expiry_that_lands_in_the_past(client):
    await make_profile(client)
    card = (await client.post("/candidate-payment-cards", json=CARD)).json()
    # Only the year is sent; the service pairs it with the stored month.
    res = await client.patch(f"/candidate-payment-cards/{card['id']}", json={"exp_year": 2021})
    assert res.status_code == 422


# ---------------------------------------------------------------- isolation

async def test_one_candidate_cannot_read_anothers_card(client):
    await make_profile(client)
    card = (await client.post("/candidate-payment-cards", json=CARD)).json()

    act_as(client, "other")
    await client.post("/candidate-profile", json={"years_experience": 0})

    assert (await client.get(f"/candidate-payment-cards/{card['id']}")).status_code == 404
    assert (await client.delete(f"/candidate-payment-cards/{card['id']}")).status_code == 404


async def test_employer_cannot_touch_candidate_cards(client):
    act_as(client, "employer")
    assert (await client.get("/candidate-payment-cards")).status_code == 403


async def test_candidate_cannot_touch_employer_cards(client):
    act_as(client, "candidate")
    assert (await client.get("/employer-payment-cards")).status_code == 403


async def test_employer_cards_need_an_employer_profile(client):
    act_as(client, "employer")
    res = await client.post("/employer-payment-cards", json=CARD)
    assert res.status_code == 404


# ------------------------------------------------------------ employer cards

async def make_employer_profile(client):
    """Seed a company straight into the database."""
    from app.companies.models import EmployerProfile

    act_as(client, "employer")
    async with client.maker() as session:
        profile = EmployerProfile(user_id=client.users["employer"].id, company_name="Acme")
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        return profile


async def test_employer_card_lifecycle(client):
    await make_employer_profile(client)

    first = await client.post("/employer-payment-cards", json=CARD)
    assert first.status_code == 201, first.text
    assert first.json()["is_default"] is True
    assert "payment_method_ref" not in first.json()

    second = await client.post(
        "/employer-payment-cards",
        json={**CARD, "payment_method_ref": "AUTH_2", "is_default": True},
    )
    assert second.status_code == 201, second.text

    listed = (await client.get("/employer-payment-cards")).json()
    assert len(listed) == 2
    assert [c["is_default"] for c in listed].count(True) == 1
    assert listed[0]["id"] == second.json()["id"]      # default sorts first

    assert (await client.delete(f"/employer-payment-cards/{second.json()['id']}")).status_code == 204
    remaining = (await client.get("/employer-payment-cards")).json()
    assert len(remaining) == 1
    assert remaining[0]["is_default"] is True          # promoted


async def test_employer_card_duplicate_token_is_a_conflict(client):
    await make_employer_profile(client)
    await client.post("/employer-payment-cards", json=CARD)
    assert (await client.post("/employer-payment-cards", json=CARD)).status_code == 409


# ========================================================= employer profile

COMPANY = {"company_name": "Acme Robotics", "company_description": "We build arms.",
           "about": "Founded in a shed.", "logo_url": "https://cdn.example.com/logo.png"}


async def make_company(client):
    act_as(client, "employer")
    return await client.post("/employer-profile", json=COMPANY)


async def test_company_create_and_read(client):
    res = await make_company(client)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["company_name"] == "Acme Robotics"
    # Trust and billing state are server-owned, and default safely.
    assert body["is_verified"] is False
    assert body["subscription_plan"] == "free"


async def test_company_cannot_be_created_twice(client):
    await make_company(client)
    assert (await client.post("/employer-profile", json=COMPANY)).status_code == 409


async def test_company_verification_and_plan_are_not_writable(client):
    await make_company(client)
    res = await client.patch(
        "/employer-profile/me",
        json={"company_name": "Acme Ltd", "is_verified": True, "subscription_plan": "premium"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["company_name"] == "Acme Ltd"      # the real field applied
    assert body["is_verified"] is False            # the injected ones ignored
    assert body["subscription_plan"] == "free"


async def test_candidate_cannot_create_a_company(client):
    act_as(client, "candidate")
    assert (await client.post("/employer-profile", json=COMPANY)).status_code == 403


async def test_founding_info_put_is_idempotent(client):
    await make_company(client)
    payload = {"industry_type": "technology", "team_size": "11-50",
               "year_of_establishment": 2015, "company_website": "https://acme.example.com"}

    first = await client.put("/employer-profile/me/founding-info", json=payload)
    assert first.status_code == 200, first.text

    second = await client.put("/employer-profile/me/founding-info",
                              json={**payload, "year_of_establishment": 2016})
    assert second.status_code == 200
    # Same row, updated -- not a second one.
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["year_of_establishment"] == 2016


async def test_founding_year_respects_the_check_constraint(client):
    await make_company(client)
    res = await client.put("/employer-profile/me/founding-info",
                           json={"year_of_establishment": 1500})
    assert res.status_code == 422


async def test_founding_info_404_before_it_is_set(client):
    await make_company(client)
    assert (await client.get("/employer-profile/me/founding-info")).status_code == 404


async def test_contact_put_is_idempotent(client):
    await make_company(client)
    first = await client.put("/employer-profile/me/contact",
                             json={"email": "careers@acme.example.com", "phone_number": "+2348000000"})
    assert first.status_code == 200, first.text
    second = await client.put("/employer-profile/me/contact",
                              json={"email": "jobs@acme.example.com"})
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["email"] == "jobs@acme.example.com"


async def test_company_social_link_is_one_per_platform(client):
    await make_company(client)
    link = {"platform": "linkedin", "url": "https://linkedin.com/company/acme"}
    assert (await client.post("/employer-profile/me/social-links", json=link)).status_code == 201
    assert (await client.post("/employer-profile/me/social-links", json=link)).status_code == 409


async def test_company_page_is_one_composite_read(client):
    created = (await make_company(client)).json()
    await client.put("/employer-profile/me/founding-info", json={"industry_type": "technology"})
    await client.put("/employer-profile/me/contact", json={"email": "careers@acme.example.com"})
    await client.post("/employer-profile/me/social-links",
                      json={"platform": "github", "url": "https://github.com/acme"})

    act_as(client, "candidate")
    res = await client.get(f"/employer-profile/{created['id']}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["founding_info"]["industry_type"] == "technology"
    assert body["contact"]["email"] == "careers@acme.example.com"
    assert len(body["social_links"]) == 1
    # The public shape is an allowlist, so internals cannot leak into it.
    assert "user_id" not in body
    assert "subscription_plan" not in body


async def test_company_page_needs_a_signed_in_user(client):
    created = (await make_company(client)).json()

    # Drop the auth stub so the real dependency runs: with no bearer token
    # the route must refuse rather than serve the company anonymously.
    app.dependency_overrides.pop(get_current_user)
    try:
        res = await client.get(f"/employer-profile/{created['id']}")
    finally:
        app.dependency_overrides[get_current_user] = lambda: _Caller.user
    assert res.status_code == 401


# =============================================================== interviews

async def seed_application(client):
    """employer -> job post -> candidate -> application, returned as ids."""
    from datetime import datetime, timedelta, timezone as tz

    from app.applications.models import Application
    from app.candidates.models import CandidateProfile
    from app.companies.models import EmployerProfile
    from app.jobs.models import JobPost

    async with client.maker() as s:
        employer = EmployerProfile(user_id=client.users["employer"].id, company_name="Acme")
        candidate = CandidateProfile(user_id=client.users["candidate"].id, years_experience=3)
        s.add_all([employer, candidate])
        await s.flush()

        job = JobPost(
            employer_id=employer.id, title="Backend Engineer", job_role="Backend",
            job_description="Build things.", salary_min=100, salary_max=200,
            salary_type="monthly", job_level="mid", experience_level="3-5_years",
            job_type="full_time", vacancies=1,
            expiration_date=datetime.now(tz.utc) + timedelta(days=30),
            country="Nigeria", city="Lagos",
        )
        s.add(job)
        await s.flush()

        application = Application(job_id=job.id, candidate_id=candidate.id)
        s.add(application)
        await s.commit()
        await s.refresh(application)
        return application.id


def future(days=7):
    from datetime import datetime, timedelta, timezone as tz
    return (datetime.now(tz.utc) + timedelta(days=days)).isoformat()


async def test_employer_books_an_interview(client):
    application_id = await seed_application(client)
    act_as(client, "employer")

    res = await client.post("/interviews", json={
        "application_id": application_id,
        "scheduled_time": future(),
        "meeting_link": "https://meet.example.com/abc",
        "notes": "Round one",
    })
    assert res.status_code == 201, res.text
    assert res.json()["application_id"] == application_id


async def test_one_interview_per_application(client):
    application_id = await seed_application(client)
    act_as(client, "employer")
    body = {"application_id": application_id, "scheduled_time": future(),
            "meeting_link": "https://meet.example.com/abc"}
    assert (await client.post("/interviews", json=body)).status_code == 201
    assert (await client.post("/interviews", json=body)).status_code == 409


async def test_meeting_link_is_required(client):
    application_id = await seed_application(client)
    act_as(client, "employer")
    res = await client.post("/interviews", json={
        "application_id": application_id, "scheduled_time": future()})
    assert res.status_code == 422


async def test_interview_cannot_be_booked_in_the_past(client):
    application_id = await seed_application(client)
    act_as(client, "employer")
    res = await client.post("/interviews", json={
        "application_id": application_id, "scheduled_time": future(-3),
        "meeting_link": "https://meet.example.com/abc"})
    assert res.status_code == 422


async def test_naive_datetime_is_rejected(client):
    application_id = await seed_application(client)
    act_as(client, "employer")
    res = await client.post("/interviews", json={
        "application_id": application_id,
        "scheduled_time": "2030-01-01T10:00:00",   # no offset
        "meeting_link": "https://meet.example.com/abc"})
    assert res.status_code == 422


async def test_employer_cannot_book_on_someone_elses_application(client):
    """The old header-based router would have allowed this outright."""
    application_id = await seed_application(client)

    from app.companies.models import EmployerProfile
    from app.users.models import User, UserRole
    async with client.maker() as s:
        intruder = User(email="e2@example.com", username="e2", hashed_password="x",
                        full_name="E Two", role=UserRole.EMPLOYER)
        s.add(intruder)
        await s.flush()
        s.add(EmployerProfile(user_id=intruder.id, company_name="Rival"))
        await s.commit()
        await s.refresh(intruder)

    _Caller.user = intruder
    res = await client.post("/interviews", json={
        "application_id": application_id, "scheduled_time": future(),
        "meeting_link": "https://meet.example.com/abc"})
    assert res.status_code == 404


async def test_candidate_can_see_their_own_interview(client):
    """The gap in the old module: the person being interviewed had no route."""
    application_id = await seed_application(client)
    act_as(client, "employer")
    booked = (await client.post("/interviews", json={
        "application_id": application_id, "scheduled_time": future(),
        "meeting_link": "https://meet.example.com/abc"})).json()

    act_as(client, "candidate")
    listed = await client.get("/interviews/me")
    assert listed.status_code == 200, listed.text
    assert [i["id"] for i in listed.json()] == [booked["id"]]

    single = await client.get(f"/interviews/{booked['id']}")
    assert single.status_code == 200
    assert single.json()["meeting_link"] == "https://meet.example.com/abc"


async def test_an_unrelated_candidate_gets_404_not_403(client):
    application_id = await seed_application(client)
    act_as(client, "employer")
    booked = (await client.post("/interviews", json={
        "application_id": application_id, "scheduled_time": future(),
        "meeting_link": "https://meet.example.com/abc"})).json()

    act_as(client, "other")
    assert (await client.get(f"/interviews/{booked['id']}")).status_code == 404


async def test_candidate_cannot_book_or_cancel(client):
    application_id = await seed_application(client)
    act_as(client, "candidate")
    assert (await client.post("/interviews", json={
        "application_id": application_id, "scheduled_time": future(),
        "meeting_link": "https://meet.example.com/abc"})).status_code == 403
    assert (await client.delete("/interviews/1")).status_code == 403


async def test_reschedule_and_cancel(client):
    application_id = await seed_application(client)
    act_as(client, "employer")
    booked = (await client.post("/interviews", json={
        "application_id": application_id, "scheduled_time": future(),
        "meeting_link": "https://meet.example.com/abc"})).json()

    moved = await client.patch(f"/interviews/{booked['id']}",
                               json={"scheduled_time": future(14), "notes": "Round two"})
    assert moved.status_code == 200, moved.text
    assert moved.json()["notes"] == "Round two"

    back = await client.patch(f"/interviews/{booked['id']}",
                              json={"scheduled_time": future(-1)})
    assert back.status_code == 422

    assert (await client.delete(f"/interviews/{booked['id']}")).status_code == 204
    assert (await client.get(f"/interviews/{booked['id']}")).status_code == 404
