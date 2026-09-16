# These hit the real Redis container on logical DB 15 (REDIS_URL, set by
# docker-compose.yml's x-test-env) — cache_service.py has no DB
# abstraction to mock against, and Redis is cheap/fast/disposable enough
# that a real instance is simpler and more honest than faking one.

import uuid

import pytest

from app.services import cache_service


def _key() -> str:
    return f"cache:test:{uuid.uuid4().hex}"


class TestBuildCacheKey:
    def test_same_inputs_produce_same_key(self):
        assert cache_service.build_cache_key("analytics", 1, group_by="region") == cache_service.build_cache_key(
            "analytics", 1, group_by="region"
        )

    def test_different_params_produce_different_keys(self):
        a = cache_service.build_cache_key("analytics", 1, group_by="region")
        b = cache_service.build_cache_key("analytics", 1, group_by="product")
        assert a != b

    def test_dataset_id_sits_outside_the_hash_for_pattern_invalidation(self):
        key = cache_service.build_cache_key("ai_query", 42, question="anything")
        parts = key.split(":")
        assert parts[0] == "cache"
        assert parts[1] == "ai_query"
        assert parts[2] == "42"

    def test_param_order_does_not_matter(self):
        a = cache_service.build_cache_key("analytics", 1, x="1", y="2")
        b = cache_service.build_cache_key("analytics", 1, y="2", x="1")
        assert a == b


class TestGetSetInvalidate:
    def test_get_on_missing_key_returns_none(self):
        assert cache_service.get_cached(_key()) is None

    def test_set_then_get_round_trips(self):
        key = _key()
        cache_service.set_cached(key, {"total": 600.0, "rows": 6}, ttl_seconds=30)
        assert cache_service.get_cached(key) == {"total": 600.0, "rows": 6}
        cache_service.invalidate(key)  # cleanup

    def test_invalidate_deletes_a_single_key(self):
        key = _key()
        cache_service.set_cached(key, {"v": 1}, ttl_seconds=30)
        cache_service.invalidate(key)
        assert cache_service.get_cached(key) is None

    def test_invalidate_by_pattern_deletes_all_matches(self):
        prefix = f"cache:pattern-test:{uuid.uuid4().hex}"
        keys = [f"{prefix}:{i}" for i in range(3)]
        for k in keys:
            cache_service.set_cached(k, {"v": k}, ttl_seconds=30)

        cache_service.invalidate(f"{prefix}:*")

        for k in keys:
            assert cache_service.get_cached(k) is None

    def test_invalidate_by_pattern_does_not_touch_other_keys(self):
        untouched_key = _key()
        cache_service.set_cached(untouched_key, {"v": "keep"}, ttl_seconds=30)

        other_prefix = f"cache:pattern-test:{uuid.uuid4().hex}"
        cache_service.set_cached(f"{other_prefix}:1", {"v": "gone"}, ttl_seconds=30)
        cache_service.invalidate(f"{other_prefix}:*")

        assert cache_service.get_cached(untouched_key) == {"v": "keep"}
        cache_service.invalidate(untouched_key)  # cleanup
