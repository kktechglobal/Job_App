"""End-to-end tests for the user domain, with no authentication stubbed.

tests/test_endpoints.py overrides `get_current_user` so it can exercise the
other modules without logging in. This file deliberately does not: every
request here carries a real bearer token minted by a real /auth/login, so the
whole chain -- bcrypt, JWT, token_version, is_active, require_role -- is under
test.

Administrator routes moved to tests/test_admin.py along with the domain.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from tests.conftest import make_engine

import app.models  # noqa: F401  -- registers every table on Base.metadata
from app.database.base import Base
from app.database.db import get_session
from app.main import app
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


CANDIDATE = {"email": "sam@example.com", "username": "sam", "password": "correct-horse",
             "full_name": "Sam Seeker", "role": "candidate", "accepted_terms": True}


async def register(client, **overrides):
    return await client.post("/auth/register", json={**CANDIDATE, **overrides})


async def login(client, email=CANDIDATE["email"], password=CANDIDATE["password"]):
    return await client.post("/auth/login", data={"username": email, "password": password})


async def token_for(client, **overrides):
    """Register, log in, and return an Authorization header."""
    await register(client, **overrides)
    res = await login(client,
                      overrides.get("email", CANDIDATE["email"]),
                      overrides.get("password", CANDIDATE["password"]))
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ------------------------------------------------------------- registration

async def test_register_creates_a_candidate(client):
    res = await register(client)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["email"] == "sam@example.com"
    assert body["role"] == "candidate"
    assert body["is_active"] is True
    assert body["is_email_verified"] is False
    assert "password" not in body and "hashed_password" not in body


async def test_register_can_create_an_employer(client):
    """The old schema had `role` commented out, so this was impossible."""
    res = await register(client, email="boss@example.com", username="boss", role="employer")
    assert res.status_code == 201, res.text
    assert res.json()["role"] == "employer"


async def test_nobody_can_register_themselves_as_admin(client):
    """The privilege-escalation hole: an open endpoint that accepts role."""
    res = await register(client, email="sneaky@example.com", username="sneaky", role="admin")
    assert res.status_code == 422


async def test_duplicate_email_is_a_conflict(client):
    await register(client)
    assert (await register(client)).status_code == 409


async def test_email_is_stored_lowercased(client):
    res = await register(client, email="Sam.Seeker@Example.COM", username="samseeker")
    assert res.status_code == 201
    assert res.json()["email"] == "sam.seeker@example.com"
    # ...and login is therefore case-insensitive.
    assert (await login(client, "SAM.SEEKER@EXAMPLE.COM")).status_code == 200


async def test_password_must_be_long_enough(client):
    assert (await register(client, password="short")).status_code == 422


async def test_password_longer_than_bcrypt_accepts_is_rejected(client):
    """bcrypt silently discards everything past 72 bytes. Accepting a longer
    password would mean only its first 72 bytes ever mattered."""
    assert (await register(client, password="a" * 73)).status_code == 422


async def test_the_password_is_hashed_not_stored(client):
    await register(client)
    async with client.maker() as s:
        stored = (await s.execute(select(User.hashed_password))).scalar_one()
    assert stored != CANDIDATE["password"]
    assert stored.startswith("$2b$")
    assert len(stored) == 60


# -------------------------------------------------------------------- login

async def test_login_returns_a_usable_token(client):
    await register(client)
    res = await login(client)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["access_token"]


async def test_wrong_password_and_unknown_email_are_indistinguishable(client):
    await register(client)
    wrong = await login(client, password="not-the-password")
    unknown = await login(client, email="nobody@example.com")

    assert wrong.status_code == 401
    assert unknown.status_code == 401
    # Same body, so the endpoint is not a directory of who has an account.
    assert wrong.json() == unknown.json()
    assert wrong.headers["www-authenticate"] == "Bearer"


async def test_a_deactivated_account_cannot_log_in(client):
    await register(client)
    async with client.maker() as s:
        user = (await s.execute(select(User))).scalars().one()
        user.is_active = False
        await s.commit()

    assert (await login(client)).status_code == 401


# ------------------------------------------------- the token actually works

async def test_token_unlocks_a_protected_endpoint(client):
    """The whole point: register, log in, and use the result for real."""
    headers = await token_for(client)

    res = await client.post("/candidate-profile",
                            json={"headline": "Python dev", "years_experience": 4},
                            headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["headline"] == "Python dev"


async def test_no_token_is_a_401(client):
    assert (await client.get("/users/me")).status_code == 401
    assert (await client.get("/candidate-profile/me")).status_code == 401


async def test_a_garbage_token_is_a_401(client):
    res = await client.get("/users/me", headers={"Authorization": "Bearer not.a.token"})
    assert res.status_code == 401


async def test_role_gate_uses_the_real_role(client):
    """An employer's genuine token must still be refused a candidate route."""
    headers = await token_for(client, email="boss@example.com", username="boss", role="employer")
    res = await client.get("/candidate-profile/me", headers=headers)
    assert res.status_code == 403


async def test_get_and_update_me(client):
    headers = await token_for(client)

    me = await client.get("/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["full_name"] == "Sam Seeker"

    patched = await client.patch("/users/me", json={"full_name": "Samuel Seeker"},
                                 headers=headers)
    assert patched.status_code == 200
    assert patched.json()["full_name"] == "Samuel Seeker"


# ----------------------------------------------------- logout and passwords

async def test_logout_invalidates_the_token(client):
    headers = await token_for(client)
    assert (await client.get("/users/me", headers=headers)).status_code == 200

    assert (await client.post("/auth/logout", headers=headers)).status_code == 204

    # A stateless JWT would still be accepted here. token_version is what stops it.
    assert (await client.get("/users/me", headers=headers)).status_code == 401


async def test_changing_the_password_ends_other_sessions(client):
    headers = await token_for(client)

    res = await client.post("/auth/change-password", headers=headers,
                            json={"current_password": "correct-horse",
                                  "new_password": "a-brand-new-one"})
    assert res.status_code == 200, res.text

    # The token used to make the change is dead...
    assert (await client.get("/users/me", headers=headers)).status_code == 401
    # ...and the response handed back a working replacement.
    fresh = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert (await client.get("/users/me", headers=fresh)).status_code == 200

    assert (await login(client, password="a-brand-new-one")).status_code == 200
    assert (await login(client, password="correct-horse")).status_code == 401


async def test_change_password_requires_the_current_one(client):
    headers = await token_for(client)
    res = await client.post("/auth/change-password", headers=headers,
                            json={"current_password": "wrong", "new_password": "something-else"})
    assert res.status_code == 422
    # The old password still works, so nothing was changed.
    assert (await login(client)).status_code == 200


async def test_deactivating_a_user_ends_their_session_immediately(client):
    headers = await token_for(client)
    assert (await client.get("/users/me", headers=headers)).status_code == 200

    async with client.maker() as s:
        user = (await s.execute(select(User))).scalars().one()
        user.is_active = False
        await s.commit()

    assert (await client.get("/users/me", headers=headers)).status_code == 401


# ============================================ username and terms of service

async def test_username_is_stored_lowercased(client):
    res = await register(client, username="SamSeeker")
    assert res.status_code == 201, res.text
    assert res.json()["username"] == "samseeker"


async def test_a_taken_username_is_a_conflict(client):
    await register(client)
    res = await register(client, email="other@example.com", username="SAM")
    assert res.status_code == 409


@pytest.mark.parametrize("bad", ["ab", "has spaces", "has-dash", "me", "admin", "a" * 31])
async def test_invalid_usernames_are_rejected(client, bad):
    assert (await register(client, username=bad)).status_code == 422


async def test_the_terms_must_actually_be_accepted(client):
    """An unchecked box must not create an account."""
    assert (await register(client, accepted_terms=False)).status_code == 422


async def test_accepting_the_terms_is_recorded_with_a_time(client):
    """A boolean cannot answer "when", which is the only reason to record it."""
    await register(client)
    async with client.maker() as s:
        user = (await s.execute(select(User))).scalars().one()
    assert user.accepted_terms_at is not None


# ============================================================ refresh tokens

async def test_login_returns_a_refresh_token(client):
    await register(client)
    body = (await login(client)).json()
    assert body["refresh_token"]
    assert body["access_token"] != body["refresh_token"]


async def test_refresh_exchanges_for_a_new_pair(client):
    await register(client)
    first = (await login(client)).json()

    res = await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert res.status_code == 200, res.text
    second = res.json()

    # Rotation: the new refresh token must not be the one we sent.
    assert second["refresh_token"] != first["refresh_token"]

    fresh = {"Authorization": f"Bearer {second['access_token']}"}
    assert (await client.get("/auth/me", headers=fresh)).status_code == 200


async def test_a_spent_refresh_token_stops_working(client):
    await register(client)
    first = (await login(client)).json()
    await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})

    again = await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert again.status_code == 422


async def test_replaying_a_spent_token_burns_the_whole_chain(client):
    """Reuse is proof of theft: the real client already rotated past it."""
    await register(client)
    first = (await login(client)).json()
    second = (await client.post(
        "/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )).json()

    live = {"Authorization": f"Bearer {second['access_token']}"}
    assert (await client.get("/auth/me", headers=live)).status_code == 200

    # Replay the spent one.
    await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})

    # The good token and the good session are both gone.
    assert (await client.post(
        "/auth/refresh", json={"refresh_token": second["refresh_token"]}
    )).status_code == 422
    assert (await client.get("/auth/me", headers=live)).status_code == 401


async def test_a_made_up_refresh_token_is_refused(client):
    await register(client)
    assert (await client.post(
        "/auth/refresh", json={"refresh_token": "not-a-real-token"}
    )).status_code == 422


async def test_logout_kills_the_refresh_token_too(client):
    """Bumping token_version alone would let a client refresh straight back in."""
    await register(client)
    pair = (await login(client)).json()
    headers = {"Authorization": f"Bearer {pair['access_token']}"}

    assert (await client.post("/auth/logout", headers=headers)).status_code == 204
    assert (await client.post(
        "/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    )).status_code == 422


async def test_changing_the_password_kills_the_refresh_token(client):
    await register(client)
    pair = (await login(client)).json()
    headers = {"Authorization": f"Bearer {pair['access_token']}"}

    await client.post("/auth/change-password", headers=headers,
                      json={"current_password": "correct-horse",
                            "new_password": "a-brand-new-one"})
    assert (await client.post(
        "/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    )).status_code == 422


async def test_auth_me_matches_users_me(client):
    headers = await token_for(client)
    a = await client.get("/auth/me", headers=headers)
    b = await client.get("/users/me", headers=headers)
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()


# =========================================================== password reset

async def test_forgot_password_never_reveals_who_has_an_account(client):
    await register(client)
    known = await client.post("/auth/forgot-password", json={"email": "sam@example.com"})
    unknown = await client.post("/auth/forgot-password", json={"email": "nobody@example.com"})

    assert known.status_code == 202
    assert unknown.status_code == 202
    assert known.json() == unknown.json()


async def test_the_reset_link_is_queued_not_sent_inline(client):
    from app.notifications.models import Notification

    await register(client)
    await client.post("/auth/forgot-password", json={"email": "sam@example.com"})

    async with client.maker() as s:
        queued = (await s.execute(select(Notification))).scalars().all()
    assert len(queued) == 1
    assert "reset-password?token=" in queued[0].body


async def reset_token_for(client, email="sam@example.com"):
    """Pull the token out of the queued message, the way a mail client would."""
    from app.notifications.models import Notification

    await client.post("/auth/forgot-password", json={"email": email})
    async with client.maker() as s:
        row = (await s.execute(select(Notification))).scalars().all()[-1]
    return row.body.split("token=")[1].split(" ")[0]


async def test_reset_sets_the_password_and_returns_a_session(client):
    await register(client)
    token = await reset_token_for(client)

    res = await client.post("/auth/reset-password",
                            json={"token": token, "new_password": "a-brand-new-one"})
    assert res.status_code == 200, res.text
    # Handed a working session, so the user is not asked to log in again.
    fresh = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert (await client.get("/auth/me", headers=fresh)).status_code == 200

    assert (await login(client, password="a-brand-new-one")).status_code == 200
    assert (await login(client, password="correct-horse")).status_code == 401


async def test_a_reset_token_works_only_once(client):
    await register(client)
    token = await reset_token_for(client)

    assert (await client.post("/auth/reset-password",
                              json={"token": token, "new_password": "first-choice"})).status_code == 200
    assert (await client.post("/auth/reset-password",
                              json={"token": token, "new_password": "second-choice"})).status_code == 422


async def test_resetting_ends_every_existing_session(client):
    """Whoever prompted the reset may already be holding one."""
    await register(client)
    pair = (await login(client)).json()
    headers = {"Authorization": f"Bearer {pair['access_token']}"}

    token = await reset_token_for(client)
    await client.post("/auth/reset-password",
                      json={"token": token, "new_password": "a-brand-new-one"})

    assert (await client.get("/auth/me", headers=headers)).status_code == 401
    assert (await client.post(
        "/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    )).status_code == 422


async def test_an_expired_reset_token_is_refused(client):
    from datetime import datetime, timedelta, timezone as tz

    from app.auth.models import PasswordResetToken

    await register(client)
    token = await reset_token_for(client)

    async with client.maker() as s:
        row = (await s.execute(select(PasswordResetToken))).scalars().one()
        row.expires_at = datetime.now(tz.utc) - timedelta(minutes=1)
        await s.commit()

    assert (await client.post("/auth/reset-password",
                              json={"token": token, "new_password": "too-late-now"})).status_code == 422


async def test_a_made_up_reset_token_is_refused(client):
    await register(client)
    assert (await client.post("/auth/reset-password",
                              json={"token": "nope", "new_password": "whatever-here"})).status_code == 422


async def test_reset_still_enforces_password_rules(client):
    await register(client)
    token = await reset_token_for(client)
    assert (await client.post("/auth/reset-password",
                              json={"token": token, "new_password": "short"})).status_code == 422
