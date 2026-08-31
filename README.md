<div align="center">

# Job Recruitment Platform

**Candidates apply. Employers hire. Administrators approve.**

A production-shaped FastAPI job board — async all the way down, with rotating
refresh tokens and permissions enforced at the database.

<br>

![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-asyncpg-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=for-the-badge)

<br>

<table>
<tr>
<td align="center"><h2>71</h2><b>endpoints</b></td>
<td align="center"><h2>8</h2><b>domains</b></td>
<td align="center"><h2>21</h2><b>tables</b></td>
<td align="center"><h2>219</h2><b>tests passing</b></td>
</tr>
</table>

</div>

<br>

---

<br>

## Endpoints

| Domain | Count | What it covers |
|:--|:--:|:--|
| [**Auth**](#auth) | 8 | Register, login, refresh, logout, password reset |
| [**Users**](#users) | 4 | Your own account and preferences |
| [**Candidates**](#candidates) | 14 | Job-seeker profile, skills, links, saved cards |
| [**Companies**](#companies) | 17 | Company profile, founding info, contact, cards |
| [**Jobs**](#jobs) | 10 | The public board, and an employer's own postings |
| [**Applications**](#applications) | 6 | Applying, and the hiring pipeline |
| [**Interviews**](#interviews) | 6 | Booking, rescheduling, attending |
| [**Admin**](#admin) | 6 | Job approval, accounts, audit trail |

> [!IMPORTANT]
> `POST /auth/login` is **form-encoded**, not JSON, and takes your email in the
> field named `username`. Every other endpoint is JSON.
> All routes need `Authorization: Bearer <access_token>` except register,
> login, refresh, forgot-password and reset-password.

<br>

### Auth

```http
POST   /auth/register              create a candidate or employer account
POST   /auth/login                 form-encoded; returns an access + refresh pair
POST   /auth/refresh               exchange a refresh token; the old one dies
POST   /auth/logout                ends every session on the account
GET    /auth/me                    who this token belongs to
POST   /auth/change-password       returns a fresh pair
POST   /auth/forgot-password       always 202, registered or not
POST   /auth/reset-password        single-use token, 30-minute life
```

### Users

```http
GET    /users/me                   your account
PATCH  /users/me                   change your display name
GET    /users/me/settings          notification and privacy preferences
PATCH  /users/me/settings
```

### Candidates

```http
POST   /candidate-profile                              create your profile
GET    /candidate-profile/me
PATCH  /candidate-profile/me
DELETE /candidate-profile/me
GET    /candidate-profile/me/skills
GET    /candidate-profile/me/social-links
POST   /candidate-profile/me/social-links              one link per platform
DELETE /candidate-profile/me/social-links/{link_id}
GET    /candidate-profile/{profile_id}                 employers viewing a candidate

GET    /candidate-payment-cards                        default first
POST   /candidate-payment-cards
GET    /candidate-payment-cards/{card_id}
PATCH  /candidate-payment-cards/{card_id}
DELETE /candidate-payment-cards/{card_id}
```

### Companies

```http
POST   /employer-profile                               create your company
GET    /employer-profile/me
PATCH  /employer-profile/me
DELETE /employer-profile/me
GET    /employer-profile/me/founding-info
PUT    /employer-profile/me/founding-info              upsert; there is only one
GET    /employer-profile/me/contact
PUT    /employer-profile/me/contact
GET    /employer-profile/me/social-links
POST   /employer-profile/me/social-links
DELETE /employer-profile/me/social-links/{link_id}
GET    /employer-profile/{employer_id}                 the whole company, one call

GET    /employer-payment-cards
POST   /employer-payment-cards
GET    /employer-payment-cards/{card_id}
PATCH  /employer-payment-cards/{card_id}
DELETE /employer-payment-cards/{card_id}
```

### Jobs

```http
GET    /jobs                              the public board -- filter, search, paginate
GET    /jobs/{job_id}

POST   /my-jobs                           creates a draft
GET    /my-jobs                           yours, drafts and expired included
GET    /my-jobs/{job_id}
PATCH  /my-jobs/{job_id}
PATCH  /my-jobs/{job_id}/published        put it on the board, or take it off
DELETE /my-jobs/{job_id}
POST   /my-jobs/{job_id}/promotions       feature a posting
GET    /my-jobs/{job_id}/promotions
```

> A posting reaches the public board only when it is **published by its
> employer**, **approved by an administrator**, and **not yet expired**.

### Applications

```http
POST   /applications                          apply; the match score is computed here
GET    /applications/me                       a candidate's own
GET    /applications/by-job/{job_id}          an employer's applicants, best match first
GET    /applications/{application_id}
PATCH  /applications/{application_id}/status  employer only
POST   /applications/{application_id}/withdraw candidate only
```

### Interviews

```http
POST   /interviews                                    employer books
GET    /interviews/me                                 the candidate's own
GET    /interviews/by-application/{application_id}
GET    /interviews/{interview_id}                     either side
PATCH  /interviews/{interview_id}                     reschedule
DELETE /interviews/{interview_id}                     cancel
```

### Admin

```http
GET    /admin/jobs                        the moderation queue
PATCH  /admin/jobs/{job_id}/approval      approve, or withdraw an approval
GET    /admin/users
GET    /admin/users/{user_id}
PATCH  /admin/users/{user_id}/active      disabling also ends open sessions
GET    /admin/audit-log                   who did what, newest first
```

<br>

---

<br>

## Environment

Copy `.env.example` to `.env` and fill it in. `.env` is gitignored — never
commit real values.

| Variable | Required | Description |
|:--|:--:|:--|
| `DATABASE_URL` | **yes** | Async Postgres URI. The `+asyncpg` driver is required — `psycopg2` is sync and will not work. |
| `SECRET_KEY` | **yes** | Signs the JWTs. |
| `ALGORITHM` | no | Defaults to `HS256`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | Defaults to `1440` (24 h). |
| `REFRESH_TOKEN_EXPIRE_DAYS` | no | Defaults to `30`. |
| `PASSWORD_RESET_EXPIRE_MINUTES` | no | Defaults to `30`. |
| `FRONTEND_RESET_URL` | no | Where the reset email points. |
| `DB_ECHO` | no | `true` logs every SQL statement. Noisy. |

```ini
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/job_application
SECRET_KEY=generate-a-real-one
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DB_ECHO=false
```

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

> [!WARNING]
> **Two mistakes that fail quietly.**
> The setting is `SECRET_KEY`, **not** `JWT_SECRET_KEY` — an unknown key is
> ignored, so the app silently falls back to a built-in default and signs
> tokens with a public string.
> And leaving `username:password` in the URI gives you
> `password authentication failed for user "username"` at startup.

<br>

---

<br>

## Running

**1. Install**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt
```

**2. Configure**

```bash
cp .env.example .env     # then edit it
```

**3. Create the schema**

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

**4. Start it**

```bash
uvicorn app.main:app --reload
```

Interactive docs at **http://127.0.0.1:8000/docs** — the green *Authorize*
button logs you in.

<br>

### Fill it with data

```bash
python -m scripts.seed
```

Creates candidates, employers, companies, jobs, applications and interviews.
Because it drives the real endpoints, a clean run also proves the API works —
**118 calls**, and it exits non-zero naming any that fail.

> [!CAUTION]
> The seed script **drops and recreates every table**. Never point it at data
> you want to keep.

### Deliver queued email

```bash
python -m app.workers.notification_worker
```

Password reset writes its link to the notifications table. Nothing is
delivered until this is running.

### Run the tests

```bash
pytest -q
```

<div align="center">

`219 passed`

</div>
