import uuid

from app.rate_limiter import limiter


async def test_signup_429s_after_the_10_per_minute_limit(client):
    """
    RATE_LIMIT_ENABLED=false everywhere else in this suite (see
    conftest.py's module docstring) — flip the limiter on just for this
    test, exactly for its duration, so ~10+ other tests' own
    signup/login calls across the suite can't spuriously trip the real
    10/minute auth limit. /auth/signup and /auth/login are IP-keyed
    (ip_key, not user_or_ip_key) — the TestClient's requests all share
    one fake client IP, so hitting either endpoint repeatedly is enough
    to trip it without needing multiple real users.
    """
    limiter.enabled = True
    try:
        last_response = None
        for _ in range(11):
            last_response = await client.post(
                "/auth/signup", json={"email": f"rl-{uuid.uuid4().hex[:8]}@example.com", "password": "testpass123"}
            )
        assert last_response.status_code == 429
        assert "Retry-After" in last_response.headers
        assert "rate limit" in last_response.json()["detail"].lower()
    finally:
        limiter.enabled = False


async def test_requests_within_the_limit_are_not_blocked(client):
    limiter.enabled = True
    try:
        for _ in range(3):
            r = await client.post(
                "/auth/signup", json={"email": f"rl-ok-{uuid.uuid4().hex[:8]}@example.com", "password": "testpass123"}
            )
            assert r.status_code == 201
    finally:
        limiter.enabled = False
