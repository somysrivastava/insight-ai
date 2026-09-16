
import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

import app.models
from app.rate_limiter import limiter, rate_limit_exceeded_handler
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
from app.routers import bulk_upload

logger = logging.getLogger("insightai")

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

# --- Day 25: rate limiting ---
# app.state.limiter + SlowAPIMiddleware together apply limiter's
# default_limits (200/hour) to every route automatically — only routes
# needing a *different* tier get an explicit @limiter.limit(...)
# decorator (see the individual routers). RATE_LIMIT_ENABLED=false in
# .env disables enforcement entirely without touching any route code.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# --- Day 25: security headers on every response ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# --- Day 25: global request-size safety net ---
# /bulk-upload is exempt — it already enforces its own explicit 100MB
# cap (Day 24), which is deliberately more permissive than this 50MB
# default; a blanket check here would reject a legitimate 80MB bulk
# request before it ever reached that cap. Checks Content-Length only
# (cheap, no body read) — a genuine safety net, not a hard guarantee
# against a chunked-transfer request with no Content-Length header.
MAX_REQUEST_BYTES = 50 * 1024 * 1024
_SIZE_LIMIT_EXEMPT_PATHS = {"/bulk-upload"}


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path not in _SIZE_LIMIT_EXEMPT_PATHS:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_REQUEST_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request body exceeds the {MAX_REQUEST_BYTES // (1024 * 1024)}MB limit."
                    },
                )
        return await call_next(request)


app.add_middleware(RequestSizeLimitMiddleware)


# --- Day 25: strip stack traces from unhandled errors ---
# Only catches what nothing else already handles — the many existing
# `except Exception as e: raise HTTPException(500, detail=f"...: {e}")`
# blocks throughout the routers already convert their own failures
# before anything reaches here, and FastAPI's own HTTPException/
# RateLimitExceeded handlers take precedence for those. This is the
# backstop for a genuinely uncaught bug, which should never leak a raw
# traceback to a client even though it's always logged in full
# server-side.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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
app.include_router(bulk_upload.router)
