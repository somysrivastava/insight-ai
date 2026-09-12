# WHY THIS FILE EXISTS:
# A Celery task_id is a hard-to-guess UUID, but that's obscurity, not
# access control — every other per-resource endpoint in this app checks
# real ownership (see Day 12.1's dataset access-control fixes), and job
# status shouldn't be the exception. Submission endpoints record who
# submitted a job here; GET /jobs/{task_id} checks it before returning
# anything.
#
# This also doubles as existence tracking: Celery's own AsyncResult
# can't distinguish "this task_id never existed" from "this task hasn't
# started yet" (both report PENDING). A missing owner record here means
# the job never existed or its record has expired — either way, 404.

import os

import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Matches celery_app.conf.result_expires in app/worker.py — a job's
# result and its ownership record expire at the same time.
JOB_OWNER_TTL_SECONDS = 3600

_redis_client: redis.Redis | None = None


def _get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def record_job_owner(task_id: str, user_id: int) -> None:
    _get_redis_client().set(f"job_owner:{task_id}", user_id, ex=JOB_OWNER_TTL_SECONDS)


def get_job_owner(task_id: str) -> int | None:
    value = _get_redis_client().get(f"job_owner:{task_id}")
    return int(value) if value is not None else None
