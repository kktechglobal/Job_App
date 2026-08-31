"""Vacancies, applications, and the match score between them.

Nothing is stubbed: every request carries a real token from a real login.
These two domains had no working code at all before -- job_post's router and
service were empty files, and application's service imported four modules that
do not exist -- so this is their first coverage.
"""

from datetime import datetime, timedelta, timezone as tz

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from tests.conftest import make_engine

import app.models  # noqa: F401  -- registers every table on Base.metadata
from app.matching import service as matching_service
from app.database.base import Base
from app.database.db import get_session
from app.jobs.models import JobPost
from app.main import app
from app.users.enums import UserRole
from app.users.models import User

PASSWORD = "correct-horse"


@pytest_asyncio.fixture
async def client():
    engine = make_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.maker = maker
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


def future(days=30):
    return (datetime.now(tz.utc) + timedelta(days=days)).isoformat()


JOB = {
    "title": "Backend Engineer", "job_role": "Backend",
    "job_description": "Build and run the API.",
    "salary_min": "300000.00", "salary_max": "500000.00",
    "currency": "NGN", "salary_type": "monthly",
    "job_level": "mid", "experience_level": "3-5_years", "job_type": "full_time",
    "vacancies": 2, "expiration_date": future(),
    "fully_remote": False, "country": "Nigeria", "city": "Lagos",
    "job_benefits": ["health", "laptop"],
    "required_skills": ["Python", "python", " FastAPI "],
}


async def account(client, email, role, password=PASSWORD):
    # Pad short handles: "hr" is a valid email local-part but too short to be
    # a username.
    handle = (email.split("@")[0].replace(".", "_") + "_user")[:30]
    body = {"email": email, "username": handle,
            "password": password, "full_name": email.split("@")[0],
            "role": role.value, "accepted_terms": True}
    res = await client.post("/auth/register", json=body)
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def auth(client, email, password=PASSWORD):
    res = await client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def employer_with_company(client, email="boss@example.com"):
    await account(client, email, UserRole.EMPLOYER)
    headers = await auth(client, email)
    res = await client.post("/employer-profile", headers=headers,
                            json={"company_name": "Acme Robotics"})
    assert res.status_code == 201, res.text
    return headers


async def candidate_with_profile(client, email="sam@example.com", skills=None):
    await account(client, email, UserRole.CANDIDATE)
    headers = await auth(client, email)
    res = await client.post("/candidate-profile", headers=headers,
                            json={"headline": "Dev", "years_experience": 4,
                                  "skills": skills if skills is not None else ["python"]})
    assert res.status_code == 201, res.text
    return headers


async def approve(client, job_id):
    """Approval is the administrator's, so it is done directly here."""
    async with client.maker() as s:
        job = (await s.execute(select(JobPost).where(JobPost.id == job_id))).scalars().one()
        job.is_approved_by_admin = True
        await s.commit()


async def live_job(client, employer_headers, **overrides):
    created = await client.post("/my-jobs", headers=employer_headers, json={**JOB, **overrides})
    assert created.status_code == 201, created.text
    job_id = created.json()["id"]
    await client.patch(f"/my-jobs/{job_id}/published?is_published=true", headers=employer_headers)
    await approve(client, job_id)
    return job_id


# ------------------------------------------------------------------- matching

def test_a_job_asking_for_nothing_is_matched_by_everyone():
    """Scoring 0 here would rank open-requirement jobs last, which is backwards."""
    assert matching_service.score(["python"], []) == 100.0


def test_score_is_the_share_of_what_the_job_asked_for():
    assert matching_service.score(["python", "sql"], ["python", "sql", "go", "rust"]) == 50.0


def test_extra_candidate_skills_do_not_dilute_a_match():
    """The denominator is what the job wants, not what the candidate has."""
    held = ["python", "sql", "cobol", "fortran", "excel"]
    assert matching_service.score(held, ["python", "sql"]) == 100.0


def test_matching_is_case_insensitive():
    assert matching_service.score(["Python"], ["PYTHON"]) == 100.0


def test_breakdown_names_what_is_missing():
    out = matching_service.breakdown(["python"], ["python", "go", "terraform"])
    assert out.matched == ["python"]
    assert out.missing == ["go", "terraform"]
    assert out.required_total == 3


# ----------------------------------------------------------------- creating

async def test_employer_creates_a_draft(client):
    headers = await employer_with_company(client)
    res = await client.post("/my-jobs", headers=headers, json=JOB)
    assert res.status_code == 201, res.text
    body = res.json()

    assert body["title"] == "Backend Engineer"
    assert body["is_published"] is False          # a draft, not on the board
    assert body["is_approved_by_admin"] is False
    assert body["required_skills"] == ["python", "fastapi"]   # deduped, lowercased


async def test_an_employer_cannot_approve_their_own_posting(client):
    """is_approved_by_admin is not in the write schema, so sending it does nothing."""
    headers = await employer_with_company(client)
    res = await client.post("/my-jobs", headers=headers,
                            json={**JOB, "is_approved_by_admin": True, "is_published": True})
    assert res.status_code == 201
    assert res.json()["is_approved_by_admin"] is False
    assert res.json()["is_published"] is False


async def test_a_job_needs_a_company_first(client):
    await account(client, "boss@example.com", UserRole.EMPLOYER)
    headers = await auth(client, "boss@example.com")
    assert (await client.post("/my-jobs", headers=headers, json=JOB)).status_code == 404


async def test_candidates_cannot_post_jobs(client):
    headers = await candidate_with_profile(client)
    assert (await client.post("/my-jobs", headers=headers, json=JOB)).status_code == 403


@pytest.mark.parametrize("bad,field", [
    ({"salary_min": "900000.00"}, "salary range"),
    ({"expiration_date": (datetime.now(tz.utc) - timedelta(days=1)).isoformat()}, "past expiry"),
    ({"expiration_date": "2099-01-01T10:00:00"}, "naive datetime"),
    ({"vacancies": 0}, "zero vacancies"),
])
async def test_incoherent_jobs_are_rejected(client, bad, field):
    headers = await employer_with_company(client)
    res = await client.post("/my-jobs", headers=headers, json={**JOB, **bad})
    assert res.status_code == 422, f"{field}: {res.status_code}"


# ------------------------------------------------------------- the board

async def test_a_draft_is_not_on_the_board(client):
    headers = await employer_with_company(client)
    await client.post("/my-jobs", headers=headers, json=JOB)

    seeker = await candidate_with_profile(client)
    assert (await client.get("/jobs", headers=seeker)).json() == []


async def test_publishing_alone_is_not_enough(client):
    """Published but unapproved stays off the board."""
    headers = await employer_with_company(client)
    job_id = (await client.post("/my-jobs", headers=headers, json=JOB)).json()["id"]
    await client.patch(f"/my-jobs/{job_id}/published?is_published=true", headers=headers)

    seeker = await candidate_with_profile(client)
    assert (await client.get("/jobs", headers=seeker)).json() == []

    await approve(client, job_id)
    assert len((await client.get("/jobs", headers=seeker)).json()) == 1


async def test_an_expired_job_drops_off_the_board(client):
    headers = await employer_with_company(client)
    job_id = await live_job(client, headers)

    async with client.maker() as s:
        job = (await s.execute(select(JobPost).where(JobPost.id == job_id))).scalars().one()
        job.expiration_date = datetime.now(tz.utc) - timedelta(days=1)
        await s.commit()

    seeker = await candidate_with_profile(client)
    assert (await client.get("/jobs", headers=seeker)).json() == []
    # ...but the employer still sees it in their own list.
    assert len((await client.get("/my-jobs", headers=headers)).json()) == 1


async def test_search_filters(client):
    headers = await employer_with_company(client)
    await live_job(client, headers)
    await live_job(client, headers, title="Remote Designer", job_role="Design",
                   fully_remote=True, city="Abuja", job_type="contract",
                   required_skills=["figma"])
    seeker = await candidate_with_profile(client)

    assert len((await client.get("/jobs", headers=seeker)).json()) == 2
    assert len((await client.get("/jobs?fully_remote=true", headers=seeker)).json()) == 1
    assert len((await client.get("/jobs?city=lagos", headers=seeker)).json()) == 1
    assert len((await client.get("/jobs?job_type=contract", headers=seeker)).json()) == 1
    assert len((await client.get("/jobs?q=designer", headers=seeker)).json()) == 1
    assert len((await client.get("/jobs?skill=figma", headers=seeker)).json()) == 1


async def test_salary_search_matches_the_top_of_the_range(client):
    """A 300k-500k job must answer a "pays at least 400k" search."""
    headers = await employer_with_company(client)
    await live_job(client, headers)
    seeker = await candidate_with_profile(client)

    assert len((await client.get("/jobs?salary_min=400000", headers=seeker)).json()) == 1
    assert len((await client.get("/jobs?salary_min=600000", headers=seeker)).json()) == 0


async def test_the_board_needs_a_signed_in_user(client):
    assert (await client.get("/jobs")).status_code == 401


# ------------------------------------------------------------- ownership

async def test_an_employer_cannot_touch_another_companys_job(client):
    owner = await employer_with_company(client)
    job_id = await live_job(client, owner)

    rival = await employer_with_company(client, "rival@example.com")
    assert (await client.get(f"/my-jobs/{job_id}", headers=rival)).status_code == 404
    assert (await client.patch(f"/my-jobs/{job_id}", headers=rival,
                               json={"title": "Mine now"})).status_code == 404
    assert (await client.delete(f"/my-jobs/{job_id}", headers=rival)).status_code == 404


async def test_patch_revalidates_the_salary_range_against_stored_values(client):
    headers = await employer_with_company(client)
    job_id = (await client.post("/my-jobs", headers=headers, json=JOB)).json()["id"]
    # Only the floor is sent; it is checked against the stored ceiling.
    res = await client.patch(f"/my-jobs/{job_id}", headers=headers,
                             json={"salary_min": "900000.00"})
    assert res.status_code == 422


async def test_promotion_payment_reference_is_unique(client):
    headers = await employer_with_company(client)
    job_id = await live_job(client, headers)
    body = {"plan": "featured", "amount_paid": "5000.00", "payment_reference": "PAY_1"}

    assert (await client.post(f"/my-jobs/{job_id}/promotions", headers=headers,
                              json=body)).status_code == 201
    assert (await client.post(f"/my-jobs/{job_id}/promotions", headers=headers,
                              json=body)).status_code == 409


# ---------------------------------------------------------- applications

async def test_candidate_applies_and_gets_a_match_score(client):
    boss = await employer_with_company(client)
    job_id = await live_job(client, boss)                    # wants python + fastapi
    seeker = await candidate_with_profile(client, skills=["python"])

    res = await client.post("/applications", headers=seeker,
                            json={"job_id": job_id, "cover_letter": "Hello"})
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "submitted"
    assert res.json()["match_score"] == 50.0                 # 1 of 2


async def test_cannot_apply_to_a_job_that_is_not_live(client):
    boss = await employer_with_company(client)
    job_id = (await client.post("/my-jobs", headers=boss, json=JOB)).json()["id"]
    seeker = await candidate_with_profile(client)

    res = await client.post("/applications", headers=seeker, json={"job_id": job_id})
    assert res.status_code == 422


async def test_applying_twice_is_a_conflict(client):
    boss = await employer_with_company(client)
    job_id = await live_job(client, boss)
    seeker = await candidate_with_profile(client)

    assert (await client.post("/applications", headers=seeker,
                              json={"job_id": job_id})).status_code == 201
    assert (await client.post("/applications", headers=seeker,
                              json={"job_id": job_id})).status_code == 409


async def test_employer_sees_applicants_best_match_first(client):
    boss = await employer_with_company(client)
    job_id = await live_job(client, boss)

    weak = await candidate_with_profile(client, "weak@example.com", skills=["python"])
    strong = await candidate_with_profile(client, "strong@example.com",
                                          skills=["python", "fastapi"])
    await client.post("/applications", headers=weak, json={"job_id": job_id})
    await client.post("/applications", headers=strong, json={"job_id": job_id})

    listed = await client.get(f"/applications/by-job/{job_id}", headers=boss)
    assert listed.status_code == 200, listed.text
    scores = [a["match_score"] for a in listed.json()]
    assert scores == [100.0, 50.0]


async def test_an_employer_cannot_read_another_companys_applicants(client):
    boss = await employer_with_company(client)
    job_id = await live_job(client, boss)
    seeker = await candidate_with_profile(client)
    await client.post("/applications", headers=seeker, json={"job_id": job_id})

    rival = await employer_with_company(client, "rival@example.com")
    assert (await client.get(f"/applications/by-job/{job_id}",
                             headers=rival)).status_code == 404


async def test_status_moves_and_then_freezes(client):
    boss = await employer_with_company(client)
    job_id = await live_job(client, boss)
    seeker = await candidate_with_profile(client)
    app_id = (await client.post("/applications", headers=seeker,
                                json={"job_id": job_id})).json()["id"]

    moved = await client.patch(f"/applications/{app_id}/status", headers=boss,
                               json={"status": "shortlisted"})
    assert moved.status_code == 200
    assert moved.json()["status"] == "shortlisted"

    await client.patch(f"/applications/{app_id}/status", headers=boss,
                       json={"status": "rejected"})
    # Rejected is final: reopening it would rewrite a decision already sent.
    again = await client.patch(f"/applications/{app_id}/status", headers=boss,
                               json={"status": "shortlisted"})
    assert again.status_code == 422


async def test_an_employer_cannot_withdraw_on_the_candidates_behalf(client):
    boss = await employer_with_company(client)
    job_id = await live_job(client, boss)
    seeker = await candidate_with_profile(client)
    app_id = (await client.post("/applications", headers=seeker,
                                json={"job_id": job_id})).json()["id"]

    res = await client.patch(f"/applications/{app_id}/status", headers=boss,
                             json={"status": "withdrawn"})
    assert res.status_code == 422


async def test_candidate_withdraws_and_cannot_reapply(client):
    boss = await employer_with_company(client)
    job_id = await live_job(client, boss)
    seeker = await candidate_with_profile(client)
    app_id = (await client.post("/applications", headers=seeker,
                                json={"job_id": job_id})).json()["id"]

    res = await client.post(f"/applications/{app_id}/withdraw", headers=seeker)
    assert res.status_code == 200
    assert res.json()["status"] == "withdrawn"

    # The row is kept, so the unique constraint still blocks a second attempt.
    assert (await client.post("/applications", headers=seeker,
                              json={"job_id": job_id})).status_code == 409


async def test_candidates_cannot_set_their_own_status(client):
    boss = await employer_with_company(client)
    job_id = await live_job(client, boss)
    seeker = await candidate_with_profile(client)
    app_id = (await client.post("/applications", headers=seeker,
                                json={"job_id": job_id})).json()["id"]

    assert (await client.patch(f"/applications/{app_id}/status", headers=seeker,
                               json={"status": "hired"})).status_code == 403


async def test_deleting_a_job_takes_its_applications_with_it(client):
    boss = await employer_with_company(client)
    job_id = await live_job(client, boss)
    seeker = await candidate_with_profile(client)
    await client.post("/applications", headers=seeker, json={"job_id": job_id})

    assert (await client.delete(f"/my-jobs/{job_id}", headers=boss)).status_code == 204
    assert (await client.get("/applications/me", headers=seeker)).json() == []
