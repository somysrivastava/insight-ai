# WHY THIS FILE EXISTS:
# Shared fixtures for the whole suite (Day 27). Deliberately does NOT
# override get_db or mock the database — DATABASE_URL/REDIS_URL are
# pointed at real, disposable containers (test-db, and redis logical DB
# 15) by docker-compose.yml's x-test-env, so every code path (FastAPI's
# own get_db, a Celery task's own SessionLocal(), a unit test arranging
# rows directly) hits the exact same real Postgres the app itself would
# use in prod — no test-only indirection to keep in sync with reality.
#
# Isolation between tests is a TRUNCATE, not a rolled-back transaction:
# Celery tasks (app/tasks/*.py) open their own SessionLocal() and commit
# for real, on a connection the test's own session knows nothing about,
# so a SAVEPOINT wrapped around just the test's session would leave
# task-committed rows behind. Truncating every table after each test
# is simpler and correct regardless of how many independent sessions a
# test touches.
#
# Only OpenAI, SendGrid, and S3 are ever mocked (see openai_mock /
# sendgrid_mock / s3_mock below) — never hit a real third-party API
# from a test.

import json
import uuid
from typing import AsyncIterator
from unittest.mock import MagicMock

import httpx2 as httpx
import pytest
from sqlalchemy import text

from app.database import Base, engine, SessionLocal
from app.main import app
from app.services import cache_service

SAMPLE_CSV = (
    b"region,product,revenue,units,order_date\n"
    b"West,Widget,1200.50,10,2024-01-05\n"
    b"East,Widget,980.25,8,2024-01-06\n"
    b"West,Gadget,4500.00,30,2024-02-11\n"
    b"East,Gadget,3100.75,22,2024-02-14\n"
    b"West,Widget,1580.00,12,2024-03-02\n"
    b"East,Gadget,2900.00,19,2024-03-20\n"
)

# Same column set as SAMPLE_CSV, different values — used by version-push
# tests (a push must keep the same columns) and by anything that needs a
# visibly different snapshot of "the same shape of data".
SAMPLE_CSV_V2 = (
    b"region,product,revenue,units,order_date\n"
    b"West,Widget,1400.00,11,2024-04-01\n"
    b"East,Widget,1010.00,9,2024-04-02\n"
    b"West,Gadget,4700.00,31,2024-04-11\n"
)

# A column removed relative to SAMPLE_CSV — used to prove push_new_version
# rejects a structurally different file.
SAMPLE_CSV_BAD_COLUMNS = b"region,product,revenue\nWest,Widget,1200.50\n"


@pytest.fixture(autouse=True)
def _clean_db():
    """
    Runs after every test — see module docstring for why this is a
    TRUNCATE rather than a rolled-back transaction. Also flushes Redis
    logical DB 15 (cache_service.py's cached results, job_service.py's
    job-ownership records) — without this, RESTART IDENTITY resetting
    dataset/user ids back to 1 each test would let a later test's
    request collide with an earlier test's still-live cache key and
    silently get served a stale cached (mocked) result instead of
    actually exercising the code under test.
    """
    yield
    with engine.begin() as conn:
        table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    cache_service._get_redis_client().flushdb()


@pytest.fixture
def db():
    """A plain session for arranging/asserting DB state directly in a test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def signup_and_login(client: httpx.AsyncClient, email: str | None = None, password: str = "testpass123") -> dict:
    """Real signup -> real login, through the app itself — not a DB
    shortcut, so the returned user also has the org/workspace/membership
    rows signup itself creates."""
    email = email or f"user-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post("/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    user_id = r.json()["user_id"]
    r = await client.post("/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {
        "user_id": user_id,
        "email": email,
        "password": password,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
async def authed(client) -> dict:
    """One signed-up user with a real bearer token."""
    return await signup_and_login(client)


@pytest.fixture
async def other_authed(client) -> dict:
    """A second, independent user in a separate workspace — for
    cross-workspace-denial (403) tests."""
    return await signup_and_login(client)


async def upload_sample_dataset(
    client: httpx.AsyncClient, headers: dict, csv_bytes: bytes = SAMPLE_CSV, filename: str = "sales.csv"
) -> dict:
    files = {"file": (filename, csv_bytes, "text/csv")}
    r = await client.post("/upload", headers=headers, files=files)
    assert r.status_code == 200, r.text
    return r.json()["dataset"]


@pytest.fixture
async def dataset(client, authed) -> dict:
    """A dataset already uploaded by `authed`, ready to query/version/export."""
    return await upload_sample_dataset(client, authed["headers"])


# --- OpenAI / SendGrid / S3 mocking — never a real network call in tests ---

def fake_chat_completion(payload: dict, tokens: int = 42) -> MagicMock:
    """Shapes a MagicMock like a real openai chat.completions.create()
    return value: response.choices[0].message.content is a JSON string,
    response.usage.total_tokens is an int — the only two things
    ai_service.py / dictionary_service.py read off it."""
    message = MagicMock(content=json.dumps(payload))
    choice = MagicMock(message=message)
    usage = MagicMock(total_tokens=tokens)
    return MagicMock(choices=[choice], usage=usage)


# A valid structured query per QUERY_SCHEMA in app/services/ai_service.py
# — "aggregate" total of the "revenue" column, every field required by
# the schema present.
DEFAULT_STRUCTURED_QUERY = {
    "operation": "aggregate",
    "column": None,
    "metric": "revenue",
    "aggregate": "sum",
    "filter_value": None,
    "filter_operator": "eq",
    "limit": 0,
    "direction": "asc",
    "explanation": "Total revenue across all records.",
}


@pytest.fixture
def openai_mock(monkeypatch) -> MagicMock:
    """Patches the lazy-singleton client accessors in both ai_service.py
    and dictionary_service.py. Defaults chat.completions.create() to a
    valid "total revenue" aggregate query; override
    openai_mock.chat.completions.create.return_value in a test for a
    different shape."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = fake_chat_completion(DEFAULT_STRUCTURED_QUERY)
    monkeypatch.setattr("app.services.ai_service._get_client", lambda: mock_client)
    monkeypatch.setattr("app.services.dictionary_service._get_client", lambda: mock_client)
    return mock_client


@pytest.fixture
def sendgrid_mock(monkeypatch) -> MagicMock:
    mock_client = MagicMock()
    mock_client.send.return_value = MagicMock(status_code=202, body=b"")
    monkeypatch.setattr("app.services.email_service._get_client", lambda: mock_client)
    return mock_client


def create_user(db, *, org=None):
    """A standalone user (+ org, if not given an existing one) with no
    workspace membership of their own — used to simulate "a rule's
    creator who no longer has access" (anomaly_service.py's
    run_alerts_for_dataset skip-on-PermissionError path)."""
    from app.models.org import Org
    from app.models.user import User
    from app.services.auth_service import hash_password

    if org is None:
        org = Org(name="Test Org")
        db.add(org)
        db.flush()

    user = User(email=f"unit-{uuid.uuid4().hex[:10]}@example.com", hashed_password=hash_password("x"), org_id=org.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_owned_dataset(db, *, row_count: int = 6, column_count: int = 5, filename: str = "sales.csv") -> "Dataset":
    """
    ORM-level equivalent of upload_sample_dataset(), for unit tests that
    need a real Dataset row (FK-valid org/workspace/user chain) without
    going through the HTTP layer or writing an actual file — used by
    version_service unit tests, which only need row/column bookkeeping,
    not a real file on disk.
    """
    from app.models.dataset import Dataset
    from app.models.org import Org
    from app.models.user import User
    from app.models.workspace import Workspace
    from app.models.workspace_member import WorkspaceMember
    from app.services.auth_service import hash_password

    org = Org(name="Test Org")
    db.add(org)
    db.flush()

    workspace = Workspace(org_id=org.id, name="Default")
    db.add(workspace)
    db.flush()

    user = User(email=f"unit-{uuid.uuid4().hex[:10]}@example.com", hashed_password=hash_password("x"), org_id=org.id)
    db.add(user)
    db.flush()

    db.add(WorkspaceMember(user_id=user.id, workspace_id=workspace.id, role="owner"))

    dataset = Dataset(
        user_id=user.id,
        workspace_id=workspace.id,
        filename=filename,
        file_path=f"{workspace.id}/{filename}",
        row_count=row_count,
        column_count=column_count,
        current_version_number=1,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@pytest.fixture
def s3_mock(monkeypatch) -> MagicMock:
    """s3_service.py builds its boto3 client at import time (module-level
    `s3_client = boto3.client(...)`), not lazily — patch that attribute
    directly rather than a factory function."""
    mock_client = MagicMock()
    monkeypatch.setattr("app.services.s3_service.s3_client", mock_client)
    return mock_client
