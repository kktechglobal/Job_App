"""What each role may and may not do.

The other suites test features; this one tests the boundaries between them. It
is written as a matrix rather than prose because the interesting property is
exhaustive: for every protected endpoint, the two roles that should NOT reach
it must be refused.

Status codes carry meaning here:

    403  the role is wrong -- require_role refused it
    404  the role is right, but the caller has no profile yet, or the row is
         not theirs. A "not yours" must look identical to "does not exist".
    200  allowed
"""

from datetime import datetime, timedelta, timezone as tz

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from tests.conftest import make_engine

import app.models  # noqa: F401  -- registers every table on Base.metadata
from app.database.base import Base
from app.database.db import get_session
from app.jobs.models import JobPost
from app.main import app
from app.users.enums import UserRole
from app.users.models import User

PASSWORD = "correct-horse-battery"


@pytest_asyncio.fixture
async def client():
    engine = make_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = __import__("sqlalchemy.ext.asyncio", fromlist=["async_sessionmaker"]) \
        .async_sessionmaker(engine, expire_on_commit=False)

    async def _session():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.maker = maker
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def register(client, email, username, role):
    return await client.post("/auth/register", json={
        "email": email, "username": username, "password": PASSWORD,
        "full_name": username.title(), "role": role, "accepted_terms": True,
    })


async def auth(client, email):
    res = await client.post("/auth/login",
                            data={"username": email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest_asyncio.fixture
async def roles(client):
    """One signed-in account of each role, admin promoted directly."""
    await register(client, "cand@example.com", "cand", "candidate")
    await register(client, "emp@example.com", "emp", "employer")
    await register(client, "root@example.com", "root", "candidate")

    async with client.maker() as s:
        admin = (await s.execute(
            select(User).where(User.email == "root@example.com"))).scalars().one()
        admin.role = UserRole.ADMIN
        await s.commit()

    return {
        "candidate": await auth(client, "cand@example.com"),
        "employer": await auth(client, "emp@example.com"),
        "admin": await auth(client, "root@example.com"),
    }


# ============================================ choosing a role at registration

@pytest.mark.parametrize("role", ["candidate", "employer"])
async def test_a_user_chooses_candidate_or_employer(client, role):
    res = await register(client, f"{role}@pick.example.com", f"{role}pick", role)
    assert res.status_code == 201, res.text
    assert res.json()["role"] == role


async def test_nobody_can_choose_admin(client):
    """The only role that cannot be self-assigned. An open endpoint that
    accepts it lets anyone mint an administrator."""
    res = await register(client, "sneak@example.com", "sneak", "admin")
    assert res.status_code == 422


async def test_an_unknown_role_is_refused(client):
    res = await register(client, "odd@example.com", "odd", "superuser")
    assert res.status_code == 422


async def test_role_defaults_to_candidate(client):
    res = await client.post("/auth/register", json={
        "email": "plain@example.com", "username": "plain", "password": PASSWORD,
        "full_name": "Plain", "accepted_terms": True,
    })
    assert res.status_code == 201
    assert res.json()["role"] == "candidate"


# ================================================= an employer builds a company

async def test_an_employer_creates_their_company_in_the_app(client, roles):
    """Nothing pre-provisions a company -- the employer creates it here."""
    emp = roles["employer"]
    assert (await client.get("/employer-profile/me", headers=emp)).status_code == 404

    made = await client.post("/employer-profile", headers=emp,
                             json={"company_name": "Acme Robotics"})
    assert made.status_code == 201, made.text
    assert made.json()["company_name"] == "Acme Robotics"
    assert (await client.get("/employer-profile/me", headers=emp)).status_code == 200


async def test_an_employer_cannot_post_a_job_before_the_company_exists(client, roles):
    res = await client.post("/my-jobs", headers=roles["employer"], json={
        "title": "Too early", "job_role": "Backend", "job_description": "x",
        "salary_min": "1.00", "salary_max": "2.00", "salary_type": "monthly",
        "job_level": "mid", "experience_level": "3-5_years", "job_type": "full_time",
        "vacancies": 1, "country": "NG", "city": "Lagos",
        "expiration_date": (datetime.now(tz.utc) + timedelta(days=10)).isoformat(),
    })
    assert res.status_code == 404


async def test_one_company_per_employer(client, roles):
    emp = roles["employer"]
    await client.post("/employer-profile", headers=emp, json={"company_name": "Acme"})
    again = await client.post("/employer-profile", headers=emp,
                              json={"company_name": "Acme Again"})
    assert again.status_code == 409


async def test_a_candidate_cannot_create_a_company(client, roles):
    res = await client.post("/employer-profile", headers=roles["candidate"],
                            json={"company_name": "Not Mine"})
    assert res.status_code == 403


# ================================================== the admin's job is approval

async def test_only_an_admin_approves_a_job(client, roles):
    emp, admin = roles["employer"], roles["admin"]
    await client.post("/employer-profile", headers=emp, json={"company_name": "Acme"})
    job = (await client.post("/my-jobs", headers=emp, json={
        "title": "Backend Engineer", "job_role": "Backend",
        "job_description": "Build things.", "salary_min": "100.00",
        "salary_max": "200.00", "salary_type": "monthly", "job_level": "mid",
        "experience_level": "3-5_years", "job_type": "full_time", "vacancies": 1,
        "country": "NG", "city": "Lagos",
        "expiration_date": (datetime.now(tz.utc) + timedelta(days=30)).isoformat(),
        "required_skills": ["python"],
    })).json()

    # the employer publishes, but that is not enough to reach the board
    await client.patch(f"/my-jobs/{job['id']}/published?is_published=true", headers=emp)
    assert (await client.get("/jobs", headers=roles["candidate"])).json() == []

    # neither of the other roles may approve
    for who in ("candidate", "employer"):
        res = await client.patch(f"/admin/jobs/{job['id']}/approval",
                                 headers=roles[who], json={"is_approved": True})
        assert res.status_code == 403, who

    ok = await client.patch(f"/admin/jobs/{job['id']}/approval", headers=admin,
                            json={"is_approved": True})
    assert ok.status_code == 200
    assert len((await client.get("/jobs", headers=roles["candidate"])).json()) == 1

    async with client.maker() as s:
        row = (await s.execute(select(JobPost).where(JobPost.id == job["id"]))).scalars().one()
    assert row.is_approved_by_admin is True


async def test_an_admin_cannot_post_or_apply(client, roles):
    """Approval is the admin's job. Being an administrator is not a superset of
    being an employer -- require_role uses strict equality on purpose."""
    admin = roles["admin"]
    assert (await client.post("/employer-profile", headers=admin,
                              json={"company_name": "Admin Co"})).status_code == 403
    assert (await client.post("/candidate-profile", headers=admin,
                              json={"years_experience": 1})).status_code == 403
    assert (await client.post("/applications", headers=admin,
                              json={"job_id": 1})).status_code == 403


async def test_an_admin_may_still_browse_the_board(client, roles):
    """The board only requires a signed-in user, not a particular role."""
    assert (await client.get("/jobs", headers=roles["admin"])).status_code == 200


# ============================================================ the full matrix

CANDIDATE_ONLY = [
    ("POST", "/candidate-profile"),
    ("GET", "/candidate-profile/me"),
    ("GET", "/candidate-payment-cards"),
    ("GET", "/applications/me"),
    ("GET", "/interviews/me"),
]

EMPLOYER_ONLY = [
    ("POST", "/employer-profile"),
    ("GET", "/employer-profile/me"),
    ("GET", "/employer-payment-cards"),
    ("GET", "/my-jobs"),
    ("POST", "/interviews"),
]

ADMIN_ONLY = [
    ("GET", "/admin/users"),
    ("GET", "/admin/jobs"),
    ("GET", "/admin/audit-log"),
]


@pytest.mark.parametrize("method,path", CANDIDATE_ONLY)
@pytest.mark.parametrize("who", ["employer", "admin"])
async def test_candidate_routes_refuse_other_roles(client, roles, method, path, who):
    res = await client.request(method, path, headers=roles[who], json={})
    assert res.status_code == 403, f"{who} reached {method} {path}"


@pytest.mark.parametrize("method,path", EMPLOYER_ONLY)
@pytest.mark.parametrize("who", ["candidate", "admin"])
async def test_employer_routes_refuse_other_roles(client, roles, method, path, who):
    res = await client.request(method, path, headers=roles[who], json={})
    assert res.status_code == 403, f"{who} reached {method} {path}"


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
@pytest.mark.parametrize("who", ["candidate", "employer"])
async def test_admin_routes_refuse_other_roles(client, roles, method, path, who):
    res = await client.request(method, path, headers=roles[who])
    assert res.status_code == 403, f"{who} reached {method} {path}"


@pytest.mark.parametrize("method,path", CANDIDATE_ONLY + EMPLOYER_ONLY + ADMIN_ONLY)
async def test_every_protected_route_refuses_an_anonymous_caller(client, method, path):
    res = await client.request(method, path, json={})
    assert res.status_code == 401, f"{method} {path} served an anonymous caller"
