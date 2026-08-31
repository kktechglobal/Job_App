"""Application entry point: creates the app, wires startup/shutdown, and
includes the routers. No business logic or route bodies live here.

Domains with more than one API surface keep each in its own module: jobs/board
is what anyone signed in can search, jobs/management is what an employer does
to their own postings -- two audiences, two gates, two files.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database.db import init_models, dispose_engine

from app.admin import router as admin
from app.applications import router as applications
from app.auth import router as auth
from app.candidates.cards import router as candidate_cards
from app.candidates.profile import router as candidate_profile
from app.companies.cards import router as employer_cards
from app.companies.profile import router as companies
from app.interviews import router as interviews
from app.jobs.board import router as job_board
from app.jobs.management import router as job_management
from app.users import router as users


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    yield
    await dispose_engine()


app = FastAPI(title="Job Recruitment Platform", lifespan=lifespan)

# Identity first, then the two account types, then what they do to each other.
app.include_router(auth.router)
app.include_router(users.router)

app.include_router(candidate_profile.router)
app.include_router(candidate_cards.router)

app.include_router(companies.router)
app.include_router(employer_cards.router)

app.include_router(job_board.router)
app.include_router(job_management.router)
app.include_router(applications.router)
app.include_router(interviews.router)

app.include_router(admin.router)


@app.get("/", tags=["meta"])
async def root():
    return {"status": "ok", "docs": "/docs"}
