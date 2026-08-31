"""Populate every table and exercise every endpoint.

Run it against whatever DATABASE_URL points at:

    python -m scripts.seed

It does two jobs at once. It fills the database with a coherent set of rows --
admins, employers, candidates, companies, jobs, applications, interviews --
so there is something to look at in /docs. And because it reaches almost all
of that through the real HTTP routes rather than the ORM, a green run is also
a smoke test: if a route, schema or permission is broken, this fails loudly
and names the endpoint.

Two things it does NOT do over HTTP, on purpose:

  * the first administrator is written directly, because /auth/register
    refuses the ADMIN role -- that refusal is the point of the endpoint;
  * job approval is done as that administrator, through /admin, which is the
    only way a posting is supposed to reach the public board.

Re-running it drops and recreates the schema, so never point it at a database
you care about.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import models as m  # noqa: F401  -- registers every table on Base.metadata
from app.database.base import Base
from app.database.db import AsyncSessionLocal, engine
from app.global_enums import CardBrand, PaymentProvider
from app.main import app
from app.users.enums import UserRole
from app.users.models import User

PASSWORD = "correct-horse-battery"
CALLS: list[tuple[str, str, int, int, bool]] = []


def future(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


async def call(client, method, path, expect=200, **kw):
    """Every request goes through here so the summary is complete."""
    res = await client.request(method, path, **kw)
    ok = res.status_code == expect
    CALLS.append((method, path, res.status_code, expect, ok))
    if not ok:
        print(f"  !! {method} {path} -> {res.status_code} (wanted {expect})")
        print(f"     {res.text[:300]}")
    return res


def bearer(res) -> dict:
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def register(client, *, email, username, name, role):
    return await call(client, "POST", "/auth/register", 201, json={
        "email": email, "username": username, "password": PASSWORD,
        "full_name": name, "role": role, "accepted_terms": True,
    })


async def login(client, email, password=PASSWORD):
    return await call(client, "POST", "/auth/login", 200,
                      data={"username": email, "password": password})


# --------------------------------------------------------------------------

async def queued_reset_token() -> str:
    """Pull the reset token out of the queued message, the way a mail client
    would. The worker has already 'delivered' it; the row keeps the body."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(m.Notification))).scalars().all()
    body = [r for r in rows if "token=" in r.body][-1].body
    return body.split("token=")[1].split(" ")[0]


async def reset_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("schema dropped and recreated")


async def make_admin(email="root@jobpilot.example.com", username="root"):
    """Written directly: /auth/register refuses the ADMIN role by design."""
    from app.auth.security import hash_password

    async with AsyncSessionLocal() as db:
        admin = User(
            email=email, username=username, full_name="Root Admin",
            hashed_password=hash_password(PASSWORD), role=UserRole.ADMIN,
            is_active=True, accepted_terms_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        await db.commit()
    print(f"admin seeded directly: {email}")


async def seed():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://seed") as c:

        # ---------------------------------------------------------- accounts
        print("\naccounts")
        await register(c, email="ada@jobpilot.example.com", username="ada",
                       name="Ada Okoro", role="candidate")
        await register(c, email="ben@jobpilot.example.com", username="ben",
                       name="Ben Adeyemi", role="candidate")
        await register(c, email="hr@acme.example.com", username="acme_hr",
                       name="Acme Recruiting", role="employer")
        await register(c, email="hr@globex.example.com", username="globex_hr",
                       name="Globex People", role="employer")

        ada = bearer(await login(c, "ada@jobpilot.example.com"))
        ben = bearer(await login(c, "ben@jobpilot.example.com"))
        acme = bearer(await login(c, "hr@acme.example.com"))
        globex = bearer(await login(c, "hr@globex.example.com"))
        root = bearer(await login(c, "root@jobpilot.example.com"))

        await call(c, "GET", "/auth/me", 200, headers=ada)
        await call(c, "GET", "/users/me", 200, headers=ada)
        await call(c, "PATCH", "/users/me", 200, headers=ada,
                   json={"full_name": "Ada Okoro"})
        await call(c, "GET", "/users/me/settings", 200, headers=ada)
        await call(c, "PATCH", "/users/me/settings", 200, headers=ada,
                   json={"job_alert_emails": False})

        # -------------------------------------------------------- candidates
        print("candidate profiles")
        await call(c, "POST", "/candidate-profile", 201, headers=ada, json={
            "headline": "Backend engineer", "bio": "Python and Postgres.",
            "years_experience": 5, "country": "Nigeria", "city": "Lagos",
            "phone_number": "+2348000000001",
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        })
        await call(c, "POST", "/candidate-profile", 201, headers=ben, json={
            "headline": "Frontend engineer", "years_experience": 2,
            "country": "Nigeria", "city": "Abuja", "skills": ["React", "Python"],
        })
        await call(c, "GET", "/candidate-profile/me", 200, headers=ada)
        await call(c, "GET", "/candidate-profile/me/skills", 200, headers=ada)
        await call(c, "PATCH", "/candidate-profile/me", 200, headers=ada,
                   json={"headline": "Senior backend engineer"})
        await call(c, "POST", "/candidate-profile/me/social-links", 201, headers=ada,
                   json={"platform": "github", "url": "https://github.com/ada"})
        await call(c, "POST", "/candidate-profile/me/social-links", 201, headers=ada,
                   json={"platform": "linkedin", "url": "https://linkedin.com/in/ada"})
        await call(c, "GET", "/candidate-profile/me/social-links", 200, headers=ada)

        card = {"provider": PaymentProvider.PAYSTACK.value, "customer_ref": "CUS_ada",
                "payment_method_ref": "AUTH_ada_1", "brand": CardBrand.VISA.value,
                "last4": "4242", "exp_month": 9, "exp_year": 2031,
                "cardholder_name": "Ada Okoro"}
        await call(c, "POST", "/candidate-payment-cards", 201, headers=ada, json=card)
        await call(c, "POST", "/candidate-payment-cards", 201, headers=ada,
                   json={**card, "payment_method_ref": "AUTH_ada_2", "last4": "1881",
                         "brand": CardBrand.MASTERCARD.value, "is_default": True})
        cards = (await call(c, "GET", "/candidate-payment-cards", 200, headers=ada)).json()
        await call(c, "GET", f"/candidate-payment-cards/{cards[0]['id']}", 200, headers=ada)
        await call(c, "PATCH", f"/candidate-payment-cards/{cards[1]['id']}", 200,
                   headers=ada, json={"cardholder_name": "A. Okoro"})

        # --------------------------------------------------------- companies
        print("companies")
        acme_co = (await call(c, "POST", "/employer-profile", 201, headers=acme, json={
            "company_name": "Acme Robotics", "company_description": "We build arms.",
            "about": "Founded in a shed.", "logo_url": "https://cdn.example.com/acme.png",
        })).json()
        await call(c, "POST", "/employer-profile", 201, headers=globex, json={
            "company_name": "Globex Corp", "company_description": "Everything, everywhere.",
        })
        await call(c, "PUT", "/employer-profile/me/founding-info", 200, headers=acme, json={
            "organization_type": "private_limited", "industry_type": "technology",
            "year_of_establishment": 2015, "team_size": "11-50",
            "company_website": "https://acme.example.com", "company_vision": "Arms for all.",
        })
        await call(c, "PUT", "/employer-profile/me/contact", 200, headers=acme, json={
            "address": "1 Marina Road, Lagos", "phone_number": "+2348000000010",
            "email": "careers@acme.example.com",
        })
        await call(c, "POST", "/employer-profile/me/social-links", 201, headers=acme,
                   json={"platform": "linkedin", "url": "https://linkedin.com/company/acme"})
        await call(c, "GET", "/employer-profile/me", 200, headers=acme)
        await call(c, "GET", "/employer-profile/me/founding-info", 200, headers=acme)
        await call(c, "GET", "/employer-profile/me/contact", 200, headers=acme)
        await call(c, "GET", "/employer-profile/me/social-links", 200, headers=acme)
        # the composite read any signed-in user gets
        await call(c, "GET", f"/employer-profile/{acme_co['id']}", 200, headers=ada)

        await call(c, "POST", "/employer-payment-cards", 201, headers=acme,
                   json={**card, "customer_ref": "CUS_acme",
                         "payment_method_ref": "AUTH_acme_1",
                         "cardholder_name": "Acme Robotics"})
        await call(c, "GET", "/employer-payment-cards", 200, headers=acme)

        # -------------------------------------------------------------- jobs
        print("jobs")
        base_job = {
            "job_role": "Backend", "job_description": "Build and run the API.",
            "salary_min": "400000.00", "salary_max": "650000.00", "currency": "NGN",
            "salary_type": "monthly", "job_level": "mid",
            "experience_level": "3-5_years", "job_type": "full_time", "vacancies": 2,
            "expiration_date": future(45), "country": "Nigeria", "city": "Lagos",
            "job_benefits": ["health", "laptop", "remote Fridays"],
        }
        live = (await call(c, "POST", "/my-jobs", 201, headers=acme, json={
            **base_job, "title": "Senior Backend Engineer",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        })).json()
        remote = (await call(c, "POST", "/my-jobs", 201, headers=acme, json={
            **base_job, "title": "Platform Engineer", "fully_remote": True,
            "city": "Remote", "job_type": "contract",
            "required_skills": ["Docker", "Python"],
        })).json()
        draft = (await call(c, "POST", "/my-jobs", 201, headers=acme, json={
            **base_job, "title": "Intern (draft)", "job_level": "entry",
            "experience_level": "none", "job_type": "internship", "vacancies": 1,
            "required_skills": ["Python"],
        })).json()
        globex_job = (await call(c, "POST", "/my-jobs", 201, headers=globex, json={
            **base_job, "title": "Frontend Engineer", "city": "Abuja",
            "required_skills": ["React"],
        })).json()

        for job, who in [(live, acme), (remote, acme), (globex_job, globex)]:
            await call(c, "PATCH", f"/my-jobs/{job['id']}/published?is_published=true",
                       200, headers=who)
        # `draft` stays unpublished on purpose, so the board can be seen to exclude it.

        print("admin approval")
        pending = (await call(c, "GET", "/admin/jobs?is_approved=false", 200,
                              headers=root)).json()
        for job in [live, remote, globex_job]:
            await call(c, "PATCH", f"/admin/jobs/{job['id']}/approval", 200, headers=root,
                       json={"is_approved": True, "note": "seeded"})
        print(f"  {pending['total']} were pending; 3 approved")

        await call(c, "GET", "/jobs", 200, headers=ada)
        await call(c, "GET", "/jobs?fully_remote=true", 200, headers=ada)
        await call(c, "GET", "/jobs?skill=python&salary_min=500000", 200, headers=ada)
        await call(c, "GET", f"/jobs/{live['id']}", 200, headers=ada)
        await call(c, "GET", "/my-jobs", 200, headers=acme)
        await call(c, "GET", f"/my-jobs/{draft['id']}", 200, headers=acme)
        await call(c, "PATCH", f"/my-jobs/{draft['id']}", 200, headers=acme,
                   json={"vacancies": 3})
        await call(c, "POST", f"/my-jobs/{live['id']}/promotions", 201, headers=acme, json={
            "plan": "featured", "featured_until": future(14),
            "amount_paid": "25000.00", "currency": "NGN", "payment_reference": "PAY_SEED_1",
        })
        await call(c, "GET", f"/my-jobs/{live['id']}/promotions", 200, headers=acme)

        # ------------------------------------------------------ applications
        print("applications")
        ada_app = (await call(c, "POST", "/applications", 201, headers=ada, json={
            "job_id": live["id"], "cover_letter": "I have shipped this exact stack.",
        })).json()
        ben_app = (await call(c, "POST", "/applications", 201, headers=ben, json={
            "job_id": live["id"], "cover_letter": "Keen to move to backend.",
        })).json()
        ben_globex_app = (await call(c, "POST", "/applications", 201, headers=ben, json={
            "job_id": globex_job["id"], "cover_letter": "React is my daily driver.",
        })).json()

        print(f"  match scores -> ada {ada_app['match_score']}, ben {ben_app['match_score']}")

        await call(c, "GET", "/applications/me", 200, headers=ada)
        await call(c, "GET", f"/applications/{ada_app['id']}", 200, headers=ada)
        ranked = (await call(c, "GET", f"/applications/by-job/{live['id']}", 200,
                             headers=acme)).json()
        print(f"  ranked best-first: {[a['match_score'] for a in ranked]}")

        await call(c, "PATCH", f"/applications/{ada_app['id']}/status", 200, headers=acme,
                   json={"status": "shortlisted"})
        await call(c, "PATCH", f"/applications/{ben_app['id']}/status", 200, headers=acme,
                   json={"status": "under_review"})

        # -------------------------------------------------------- interviews
        print("interviews")
        interview = (await call(c, "POST", "/interviews", 201, headers=acme, json={
            "application_id": ada_app["id"], "scheduled_time": future(7),
            "meeting_link": "https://meet.example.com/ada-round-1", "notes": "Round one.",
        })).json()
        await call(c, "GET", f"/interviews/{interview['id']}", 200, headers=acme)
        await call(c, "GET", "/interviews/me", 200, headers=ada)
        await call(c, "GET", f"/interviews/by-application/{ada_app['id']}", 200, headers=acme)
        await call(c, "PATCH", f"/interviews/{interview['id']}", 200, headers=acme,
                   json={"scheduled_time": future(9), "notes": "Moved to Thursday."})
        await call(c, "PATCH", f"/applications/{ada_app['id']}/status", 200, headers=acme,
                   json={"status": "interview_scheduled"})

        # ------------------------------------------------------------- admin
        print("admin")
        await call(c, "GET", "/admin/users", 200, headers=root)
        await call(c, "GET", "/admin/users?role=employer", 200, headers=root)
        await call(c, "GET", "/admin/jobs?is_approved=true", 200, headers=root)
        await call(c, "GET", "/admin/audit-log", 200, headers=root)

        # ---------------------------------------------- tokens and reset mail
        print("tokens")
        pair = (await login(c, "ben@jobpilot.example.com")).json()
        await call(c, "POST", "/auth/refresh", 200,
                   json={"refresh_token": pair["refresh_token"]})
        await call(c, "POST", "/auth/forgot-password", 202,
                   json={"email": "ben@jobpilot.example.com"})
        await call(c, "POST", "/auth/logout", 204, headers=ben)
        await call(c, "GET", "/", 200)

        # --------------------------------------------- employer-side reads
        await call(c, "GET", "/employer-profile/me", 200, headers=globex)
        await call(c, "PATCH", "/employer-profile/me", 200, headers=globex,
                   json={"about": "Everything, everywhere, all at once."})
        acme_cards = (await call(c, "GET", "/employer-payment-cards", 200,
                                 headers=acme)).json()
        await call(c, "GET", f"/employer-payment-cards/{acme_cards[0]['id']}", 200,
                   headers=acme)
        await call(c, "PATCH", f"/employer-payment-cards/{acme_cards[0]['id']}", 200,
                   headers=acme, json={"cardholder_name": "Acme Robotics Ltd"})
        # an employer reading a candidate's profile
        ada_profile = (await call(c, "GET", "/candidate-profile/me", 200,
                                  headers=ada)).json()
        await call(c, "GET", f"/candidate-profile/{ada_profile['id']}", 200, headers=acme)

        # ------------------------------------------------ password lifecycle
        print("password lifecycle")
        token = await queued_reset_token()
        await call(c, "POST", "/auth/reset-password", 200,
                   json={"token": token, "new_password": "a-brand-new-secret"})
        ben = bearer(await login(c, "ben@jobpilot.example.com", "a-brand-new-secret"))
        await call(c, "POST", "/auth/change-password", 200, headers=ben,
                   json={"current_password": "a-brand-new-secret",
                         "new_password": PASSWORD})
        ben = bearer(await login(c, "ben@jobpilot.example.com"))

        # ------------------------------------------------------- admin reads
        users = (await call(c, "GET", "/admin/users?role=candidate", 200,
                            headers=root)).json()
        await call(c, "GET", f"/admin/users/{users['items'][0]['id']}", 200, headers=root)

        # ----------------------------------------- deletes, on throwaway rows
        # Run last and against records created for the purpose, so the seeded
        # data above survives for anyone browsing /docs afterwards.
        print("deletes (throwaway records)")
        await call(c, "POST", f"/applications/{ben_globex_app['id']}/withdraw", 200,
                   headers=ben)

        temp_job = (await call(c, "POST", "/my-jobs", 201, headers=acme, json={
            **base_job, "title": "Temp posting", "required_skills": ["Python"],
        })).json()
        await call(c, "DELETE", f"/my-jobs/{temp_job['id']}", 204, headers=acme)
        await call(c, "DELETE", f"/interviews/{interview['id']}", 204, headers=acme)
        # ...then put one back, so the seeded data still has an interview in it
        # for anyone browsing /docs afterwards.
        await call(c, "POST", "/interviews", 201, headers=acme, json={
            "application_id": ada_app["id"], "scheduled_time": future(9),
            "meeting_link": "https://meet.example.com/ada-round-1",
            "notes": "Round one. Rebooked after the delete check.",
        })

        await register(c, email="zoe@jobpilot.example.com", username="zoe",
                       name="Zoe Temp", role="candidate")
        zoe = bearer(await login(c, "zoe@jobpilot.example.com"))
        await call(c, "POST", "/candidate-profile", 201, headers=zoe,
                   json={"headline": "Temp", "years_experience": 0, "skills": ["Python"]})
        link = (await call(c, "POST", "/candidate-profile/me/social-links", 201,
                           headers=zoe,
                           json={"platform": "github",
                                 "url": "https://github.com/zoe"})).json()
        zoe_card = (await call(c, "POST", "/candidate-payment-cards", 201, headers=zoe,
                               json={**card, "customer_ref": "CUS_zoe",
                                     "payment_method_ref": "AUTH_zoe_1"})).json()
        await call(c, "DELETE", f"/candidate-payment-cards/{zoe_card['id']}", 204,
                   headers=zoe)
        await call(c, "DELETE", f"/candidate-profile/me/social-links/{link['id']}", 204,
                   headers=zoe)
        await call(c, "DELETE", "/candidate-profile/me", 204, headers=zoe)

        zoe_id = (await call(c, "GET", "/auth/me", 200, headers=zoe)).json()["id"]
        await call(c, "PATCH", f"/admin/users/{zoe_id}/active", 200, headers=root,
                   json={"is_active": False, "note": "seeded throwaway"})

        await register(c, email="temp@globex.example.com", username="globex_temp",
                       name="Temp Employer", role="employer")
        temp_hr = bearer(await login(c, "temp@globex.example.com"))
        await call(c, "POST", "/employer-profile", 201, headers=temp_hr,
                   json={"company_name": "Temp Co"})
        temp_link = (await call(c, "POST", "/employer-profile/me/social-links", 201,
                                headers=temp_hr,
                                json={"platform": "website",
                                      "url": "https://temp.example.com"})).json()
        temp_card = (await call(c, "POST", "/employer-payment-cards", 201,
                                headers=temp_hr,
                                json={**card, "customer_ref": "CUS_temp",
                                      "payment_method_ref": "AUTH_temp_1"})).json()
        await call(c, "DELETE", f"/employer-payment-cards/{temp_card['id']}", 204,
                   headers=temp_hr)
        await call(c, "DELETE", f"/employer-profile/me/social-links/{temp_link['id']}", 204,
                   headers=temp_hr)
        await call(c, "DELETE", "/employer-profile/me", 204, headers=temp_hr)

    # the queued reset mail is drained by the worker, not by a request
    from app.workers import notification_worker
    sent = await notification_worker.drain_once()
    print(f"notification worker drained {sent} message(s)")


async def summarise():
    async with AsyncSessionLocal() as db:
        counts = {}
        for name, model in [
            ("users", m.User), ("candidates", m.CandidateProfile),
            ("companies", m.EmployerProfile), ("jobs", m.JobPost),
            ("applications", m.Application), ("interviews", m.Interview),
            ("skills", m.Skill), ("cards (candidate)", m.CandidateCard),
            ("cards (employer)", m.EmployerCard), ("promotions", m.JobPromotion),
            ("audit log", m.AdminActionLog), ("notifications", m.Notification),
            ("refresh tokens", m.RefreshToken), ("reset tokens", m.PasswordResetToken),
        ]:
            rows = (await db.execute(select(model))).scalars().all()
            counts[name] = len(rows)

    print("\nrows written")
    for k, v in counts.items():
        print(f"  {k:20} {v}")

    failed = [c for c in CALLS if not c[4]]
    print(f"\nendpoints exercised: {len(CALLS)}   failed: {len(failed)}")
    if failed:
        for method, path, got, want, _ in failed:
            print(f"  FAIL {method} {path} -> {got} (wanted {want})")
    return not failed


async def main():
    await reset_schema()
    await make_admin()
    await seed()
    ok = await summarise()
    await engine.dispose()
    print("\nSEED OK" if ok else "\nSEED FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
