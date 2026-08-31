"""The administrator domain, exercised with real tokens.

Like tests/test_auth.py, nothing is stubbed: an admin here has logged in for a
real token. ADMIN cannot be reached through /auth/register -- that is the
point of test_nobody_can_register_themselves_as_admin -- so admins are seeded
directly, which is how they would be made in production too.
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
from app.admin.models import AdminActionLog
from app.database.base import Base
from app.database.db import get_session
from app.companies.models import EmployerProfile
from app.jobs.models import JobPost
from app.main import app
from app.users.enums import UserRole
from app.users.models import User


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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.maker = maker
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


PASSWORD = "correct-horse"


async def make_account(client, email, role, password=PASSWORD):
    """Register through the API, then set the role directly if it is one the
    registration endpoint refuses to grant."""
    # Pad short handles: "hr" is a valid email local-part but too short to be
    # a username.
    handle = (email.split("@")[0].replace(".", "_") + "_user")[:30]
    body = {"email": email, "username": handle,
            "password": password, "full_name": email.split("@")[0],
            "role": "candidate" if role == UserRole.ADMIN else role.value,
            "accepted_terms": True}
    res = await client.post("/auth/register", json=body)
    assert res.status_code == 201, res.text

    if role == UserRole.ADMIN:
        async with client.maker() as s:
            user = (await s.execute(select(User).where(User.email == email))).scalars().one()
            user.role = UserRole.ADMIN
            await s.commit()
    return res.json()["id"]


async def auth(client, email, password=PASSWORD):
    res = await client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def seed_job(client, approved=False):
    async with client.maker() as s:
        owner = User(email="boss@example.com", username="boss", hashed_password="x",
                     full_name="Boss", role=UserRole.EMPLOYER)
        s.add(owner)
        await s.flush()
        employer = EmployerProfile(user_id=owner.id, company_name="Acme")
        s.add(employer)
        await s.flush()
        job = JobPost(
            employer_id=employer.id, title="Backend", job_role="Backend",
            job_description="Build things.", salary_min=100, salary_max=200,
            salary_type="monthly", job_level="mid", experience_level="3-5_years",
            job_type="full_time", vacancies=1,
            expiration_date=datetime.now(tz.utc) + timedelta(days=30),
            country="Nigeria", city="Lagos", is_approved_by_admin=approved,
        )
        s.add(job)
        await s.commit()
        return job.id


# ------------------------------------------------------------------ the gate

@pytest.mark.parametrize("path", [
    "/admin/users", "/admin/jobs", "/admin/audit-log", "/admin/users/1",
])
async def test_admin_routes_reject_a_candidate(client, path):
    await make_account(client, "sam@example.com", UserRole.CANDIDATE)
    headers = await auth(client, "sam@example.com")
    assert (await client.get(path, headers=headers)).status_code == 403


async def test_admin_routes_reject_an_employer(client):
    await make_account(client, "hr@example.com", UserRole.EMPLOYER)
    headers = await auth(client, "hr@example.com")
    assert (await client.get("/admin/users", headers=headers)).status_code == 403


async def test_admin_routes_need_a_token(client):
    assert (await client.get("/admin/users")).status_code == 401


# ------------------------------------------------------------------- users

async def test_admin_lists_and_filters_users(client):
    await make_account(client, "root@example.com", UserRole.ADMIN)
    await make_account(client, "sam@example.com", UserRole.CANDIDATE)
    await make_account(client, "hr@example.com", UserRole.EMPLOYER)
    headers = await auth(client, "root@example.com")

    everyone = await client.get("/admin/users", headers=headers)
    assert everyone.status_code == 200, everyone.text
    assert everyone.json()["total"] == 3

    employers = await client.get("/admin/users?role=employer", headers=headers)
    assert [u["email"] for u in employers.json()["items"]] == ["hr@example.com"]

    found = await client.get("/admin/users?search=SAM", headers=headers)
    assert [u["email"] for u in found.json()["items"]] == ["sam@example.com"]


async def test_user_list_is_paged(client):
    await make_account(client, "root@example.com", UserRole.ADMIN)
    for i in range(5):
        await make_account(client, f"user{i}@example.com", UserRole.CANDIDATE)
    headers = await auth(client, "root@example.com")

    page = await client.get("/admin/users?limit=2&offset=2", headers=headers)
    body = page.json()
    assert body["total"] == 6          # the admin plus five
    assert len(body["items"]) == 2
    assert body["offset"] == 2


async def test_admin_never_sees_a_password_hash(client):
    await make_account(client, "root@example.com", UserRole.ADMIN)
    headers = await auth(client, "root@example.com")
    body = (await client.get("/admin/users", headers=headers)).json()
    assert "hashed_password" not in body["items"][0]
    assert "password" not in body["items"][0]


async def test_deactivating_a_user_ends_their_session(client):
    await make_account(client, "root@example.com", UserRole.ADMIN)
    sam_id = await make_account(client, "sam@example.com", UserRole.CANDIDATE)

    sam = await auth(client, "sam@example.com")
    assert (await client.get("/users/me", headers=sam)).status_code == 200

    admin = await auth(client, "root@example.com")
    res = await client.patch(f"/admin/users/{sam_id}/active", headers=admin,
                             json={"is_active": False, "note": "ticket 41"})
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False

    # Not just future logins -- the token already in their hands stops working.
    assert (await client.get("/users/me", headers=sam)).status_code == 401
    assert (await client.post("/auth/login",
                              data={"username": "sam@example.com",
                                    "password": PASSWORD})).status_code == 401


async def test_reactivating_lets_them_back_in(client):
    await make_account(client, "root@example.com", UserRole.ADMIN)
    sam_id = await make_account(client, "sam@example.com", UserRole.CANDIDATE)
    admin = await auth(client, "root@example.com")

    await client.patch(f"/admin/users/{sam_id}/active", headers=admin, json={"is_active": False})
    res = await client.patch(f"/admin/users/{sam_id}/active", headers=admin, json={"is_active": True})
    assert res.status_code == 200
    assert (await auth(client, "sam@example.com")) is not None


async def test_an_admin_cannot_lock_themselves_out(client):
    admin_id = await make_account(client, "root@example.com", UserRole.ADMIN)
    headers = await auth(client, "root@example.com")

    res = await client.patch(f"/admin/users/{admin_id}/active", headers=headers,
                             json={"is_active": False})
    assert res.status_code == 422
    assert (await client.get("/users/me", headers=headers)).status_code == 200


async def test_one_admin_cannot_disable_another(client):
    await make_account(client, "root@example.com", UserRole.ADMIN)
    other_id = await make_account(client, "root2@example.com", UserRole.ADMIN)
    headers = await auth(client, "root@example.com")

    res = await client.patch(f"/admin/users/{other_id}/active", headers=headers,
                             json={"is_active": False})
    assert res.status_code == 422


async def test_unknown_user_is_a_404(client):
    await make_account(client, "root@example.com", UserRole.ADMIN)
    headers = await auth(client, "root@example.com")
    assert (await client.get("/admin/users/999", headers=headers)).status_code == 404


# -------------------------------------------------------------------- jobs

async def test_moderation_queue_lists_unapproved_jobs(client):
    await make_account(client, "root@example.com", UserRole.ADMIN)
    job_id = await seed_job(client)
    headers = await auth(client, "root@example.com")

    queue = await client.get("/admin/jobs?is_approved=false", headers=headers)
    assert queue.status_code == 200, queue.text
    assert [j["id"] for j in queue.json()["items"]] == [job_id]

    assert (await client.get("/admin/jobs?is_approved=true", headers=headers)).json()["total"] == 0


async def test_admin_approves_a_job(client):
    await make_account(client, "root@example.com", UserRole.ADMIN)
    job_id = await seed_job(client)
    headers = await auth(client, "root@example.com")

    res = await client.patch(f"/admin/jobs/{job_id}/approval", headers=headers,
                             json={"is_approved": True})
    assert res.status_code == 200, res.text
    assert res.json()["is_approved_by_admin"] is True

    async with client.maker() as s:
        job = (await s.execute(select(JobPost).where(JobPost.id == job_id))).scalars().one()
    assert job.is_approved_by_admin is True


async def test_approval_can_be_withdrawn(client):
    """The old endpoint could only set the flag true, so a mistake was final."""
    await make_account(client, "root@example.com", UserRole.ADMIN)
    job_id = await seed_job(client, approved=True)
    headers = await auth(client, "root@example.com")

    res = await client.patch(f"/admin/jobs/{job_id}/approval", headers=headers,
                             json={"is_approved": False, "note": "spam"})
    assert res.status_code == 200
    assert res.json()["is_approved_by_admin"] is False


# --------------------------------------------------------------- audit log

async def test_every_change_is_recorded(client):
    await make_account(client, "root@example.com", UserRole.ADMIN)
    sam_id = await make_account(client, "sam@example.com", UserRole.CANDIDATE)
    job_id = await seed_job(client)
    headers = await auth(client, "root@example.com")

    await client.patch(f"/admin/users/{sam_id}/active", headers=headers,
                       json={"is_active": False, "note": "ticket 41"})
    await client.patch(f"/admin/jobs/{job_id}/approval", headers=headers,
                       json={"is_approved": True})

    log = await client.get("/admin/audit-log", headers=headers)
    assert log.status_code == 200, log.text
    entries = log.json()["items"]
    assert log.json()["total"] == 2

    actions = {e["action"] for e in entries}
    assert actions == {"user_deactivated", "job_approved"}
    deactivation = next(e for e in entries if e["action"] == "user_deactivated")
    assert deactivation["target_type"] == "user"
    assert deactivation["target_id"] == sam_id
    assert deactivation["note"] == "ticket 41"


async def test_audit_log_filters_by_target(client):
    await make_account(client, "root@example.com", UserRole.ADMIN)
    sam_id = await make_account(client, "sam@example.com", UserRole.CANDIDATE)
    job_id = await seed_job(client)
    headers = await auth(client, "root@example.com")

    await client.patch(f"/admin/users/{sam_id}/active", headers=headers, json={"is_active": False})
    await client.patch(f"/admin/jobs/{job_id}/approval", headers=headers, json={"is_approved": True})

    only_jobs = await client.get("/admin/audit-log?target_type=job_post", headers=headers)
    assert [e["target_id"] for e in only_jobs.json()["items"]] == [job_id]


async def test_a_no_op_change_is_not_logged(client):
    """An audit trail full of "set it to what it already was" is one nobody reads."""
    await make_account(client, "root@example.com", UserRole.ADMIN)
    sam_id = await make_account(client, "sam@example.com", UserRole.CANDIDATE)
    headers = await auth(client, "root@example.com")

    res = await client.patch(f"/admin/users/{sam_id}/active", headers=headers,
                             json={"is_active": True})     # already active
    assert res.status_code == 200

    async with client.maker() as s:
        assert (await s.execute(select(AdminActionLog))).scalars().all() == []


async def test_the_log_records_which_admin_acted(client):
    admin_id = await make_account(client, "root@example.com", UserRole.ADMIN)
    sam_id = await make_account(client, "sam@example.com", UserRole.CANDIDATE)
    headers = await auth(client, "root@example.com")

    await client.patch(f"/admin/users/{sam_id}/active", headers=headers, json={"is_active": False})

    log = await client.get(f"/admin/audit-log?admin_id={admin_id}", headers=headers)
    assert log.json()["total"] == 1
    assert log.json()["items"][0]["admin_id"] == admin_id
