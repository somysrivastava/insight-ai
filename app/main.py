
from fastapi import FastAPI

import app.models
from app.routers import dataset, auth
from app.routers.cleaning import router as cleaning_router
from app.routers.analytics import router as analytics_router

from app.routers import visualization
from app.routers import reports
from app.routers import ai
from app.routers import jobs
from app.routers import workspaces
from app.routers import joins
from app.routers import exports
from app.routers import schedules
from app.routers import alerts
from app.routers import dashboards
from app.routers import dictionary
from app.routers import versions

app = FastAPI(
    title="Insight AI",
    description="An AI-powered platform for data analysis and insights.",
    version="1.0.0",
)

# Schema is managed by Alembic (Day 16), not create_all() — this project
# now has real foreign-key/data-migration needs that create_all() can't
# express (it only ever creates missing tables, never alters existing
# ones or backfills data). Run `alembic upgrade head` before starting
# the app. In Docker Compose, the `migrate` service does this
# automatically before `app`/`celery` start.


@app.get("/")
def home():
    return {"message": "Insights AI backend is running!"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/version")
def version():
    return {"version": "1.0.0"}


app.include_router(dataset.router)
app.include_router(auth.router)
app.include_router(cleaning_router)
app.include_router(analytics_router)
app.include_router(reports.router)
app.include_router(visualization.router)
app.include_router(ai.router)
app.include_router(jobs.router)
app.include_router(workspaces.router)
app.include_router(joins.router)
app.include_router(exports.router)
app.include_router(schedules.router)
app.include_router(alerts.router)
app.include_router(dashboards.router)
app.include_router(dictionary.router)
app.include_router(versions.router)
