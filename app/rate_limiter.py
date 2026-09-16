# WHY THIS FILE EXISTS:
# Centralizes the slowapi Limiter + key functions (Day 25) so every
# router needing a non-default tier imports from one place instead of
# reimplementing JWT-decoding for its own rate-limit key. Separate from
# app/worker.py (Celery config) — this is HTTP-request-layer config,
# unrelated to background tasks, even though both end up pointed at
# the same Redis instance.

import os

from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"


def user_or_ip_key(request: Request) -> str:
    """
    Keys by the authenticated user when a valid JWT is present, else
    falls back to IP. Keyed by the token's "sub" claim — the user's
    email, since auth_service.py never puts a numeric id in the
    token — rather than looking up the numeric id via a DB query on
    every single request just to rate-limit it. This is also what
    naturally makes an unauthenticated request IP-keyed, but see
    ip_key() below: login/signup use that explicitly, so they're
    IP-keyed unconditionally rather than by the coincidence of no
    Authorization header being sent.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer ") :]
        try:
            payload = jwt.decode(token, str(SECRET_KEY), algorithms=[str(ALGORITHM)])
            email = payload.get("sub")
            if email:
                return f"user:{email}"
        except JWTError:
            pass
    return f"ip:{get_remote_address(request)}"


def ip_key(request: Request) -> str:
    """Forced on login/signup — always IP-based, regardless of any Authorization header sent."""
    return f"ip:{get_remote_address(request)}"


# WHY EVERY @limiter.limit(...) ROUTE NEEDS BOTH request: Request AND
# response: Response PARAMETERS (found the hard way, via a real crash,
# not documentation):
# - slowapi finds the Request object by inspecting the decorated
#   function's parameters for one literally NAMED "request" — not by
#   type annotation. A body parameter also named "request" (as ai.py's
#   originally was, `request: QueryRequest`) collides; rename the body
#   param instead.
# - With headers_enabled=True (below), slowapi injects X-RateLimit-*/
#   Retry-After headers into the endpoint's OWN return value if that's
#   already a Response instance — otherwise it looks for a second
#   parameter literally named "response" (FastAPI's injectable
#   Response object) to mutate instead. Every route here returns a
#   plain dict/Pydantic model, not a raw Response, so every decorated
#   route needs `response: Response` too, or this raises a bare
#   uncaught exception on every successful (non-blocked) call to it.
limiter = Limiter(
    key_func=user_or_ip_key,
    storage_uri=REDIS_URL,
    default_limits=["200/hour"],
    enabled=RATE_LIMIT_ENABLED,
    # headers_enabled defaults to False in slowapi — without this, no
    # Retry-After (or X-RateLimit-*) headers are ever injected, found
    # by actually inspecting a real 429 response rather than assuming
    # the spec's "Retry-After header" requirement was met by default.
    headers_enabled=True,
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Deliberately synchronous, not async — slowapi's own SlowAPIMiddleware
    (used for default_limits, i.e. every route without its own
    @limiter.limit decorator) calls exception handlers synchronously and
    falls back to slowapi's own default handler if it detects an async
    one via inspect.iscoroutinefunction(). Keeping this sync is what
    makes the {"detail": ...} reshaping below actually apply on both
    paths — the default-tier (middleware) path and the decorated-route
    (raised-exception) path — not just one of them.

    Delegates to slowapi's own handler for the Retry-After computation
    (it already knows the exact window/reset math), then reshapes the
    body into this app's {"detail": ...} convention instead of
    slowapi's default shape.
    """
    slowapi_response = _rate_limit_exceeded_handler(request, exc)
    response = JSONResponse(
        status_code=slowapi_response.status_code,
        content={"detail": f"Rate limit exceeded ({exc.detail}). Try again later."},
    )
    for header, value in slowapi_response.headers.items():
        if header.lower() not in ("content-length", "content-type"):
            response.headers[header] = value
    return response
