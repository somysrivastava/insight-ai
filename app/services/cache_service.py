# WHY THIS FILE EXISTS:
# A read-through Redis cache for analytics/AI-query/report results
# (Day 25) — deliberately dumb: it knows nothing about what it's
# caching. Callers (analytics_service.py, ai_service.py,
# report_service.py) check get_cached() first, compute on a miss, then
# set_cached() the result; version_service.py invalidates by pattern
# whenever a dataset's current version changes. Same Redis instance as
# Celery/job_service.py (REDIS_URL), distinguished only by the
# "cache:" key prefix — no reason to run a second Redis for this.

import hashlib
import json
import os
from typing import Any, Optional

import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

TTL_ANALYTICS_SECONDS = 5 * 60
TTL_AI_QUERY_SECONDS = 60 * 60
TTL_REPORT_SECONDS = 5 * 60

_redis_client: redis.Redis | None = None


def _get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def build_cache_key(endpoint: str, dataset_id: int, **params: Any) -> str:
    """
    "cache:{endpoint}:{dataset_id}:{params_hash}" — params_hash covers
    whatever varies the result for a fixed endpoint+dataset (e.g.
    group_by for a breakdown, the question text for an AI query).
    dataset_id sits in the middle (not inside the hash) specifically so
    version_service.py can invalidate every cached result for one
    dataset with a single pattern, regardless of endpoint or params.
    """
    params_json = json.dumps(params, sort_keys=True, default=str)
    params_hash = hashlib.sha256(params_json.encode("utf-8")).hexdigest()[:16]
    return f"cache:{endpoint}:{dataset_id}:{params_hash}"


def get_cached(key: str) -> Optional[Any]:
    raw = _get_redis_client().get(key)
    if raw is None:
        return None
    return json.loads(raw)


def set_cached(key: str, value: Any, ttl_seconds: int) -> None:
    _get_redis_client().set(key, json.dumps(value, default=str), ex=ttl_seconds)


def invalidate(key_pattern: str) -> None:
    """Deletes every key matching key_pattern via SCAN — never the blocking KEYS command."""
    client = _get_redis_client()
    for key in client.scan_iter(match=key_pattern, count=100):
        client.delete(key)
