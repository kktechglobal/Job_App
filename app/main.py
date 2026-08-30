"""Application entry point.

Notice what is NOT here: no business logic, no SQL, no route bodies. main.py
only creates the app, defines its startup/shutdown, and plugs in the routers.
When a file's whole job fits on one screen, you can see the shape of the
project without reading any of it.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI


from app.database.db import init_models, dispose_engine


from app.users.routers import routers as users_router
from app.job_post.routers import routers as job_posts_router
from app.interview.routers import routers as interview_router   
from app.employer_profile.routers import routers as employer_profile_router
from app.application.routers import routers as application_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Everything before the yield runs once on startup...
    await init_models()
    yield
    # ...and everything after it runs once on shutdown.
    await dispose_engine()


app = FastAPI(title="Class Demo API", lifespan=lifespan)

app.include_router(users_router)
app.include_router(job_posts_router)
app.include_router(interview_router)
app.include_router(employer_profile_router)
app.include_router(application_router)






# The feed is not plugged in yet. It only makes sense once we have login, so it
# waits in reference/feed.py until we cover authentication.


@app.get("/", tags=["meta"])
async def root():
    return {"status": "ok", "docs": "/docs"}
