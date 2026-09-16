from app.services.auth_service import create_access_token
from app.tests.conftest import signup_and_login


async def test_signup_then_login_then_use_token(client):
    creds = await signup_and_login(client, email="flow-user@example.com")
    assert creds["token"]

    r = await client.get("/workspaces/", headers=creds["headers"])
    assert r.status_code == 200
    workspaces = r.json()
    # Signup auto-provisions exactly one "Default" workspace.
    assert len(workspaces) == 1
    assert workspaces[0]["name"] == "Default"
    assert workspaces[0]["role"] == "owner"


async def test_protected_endpoint_without_token_is_401(client):
    r = await client.get("/workspaces/")
    assert r.status_code == 401


async def test_protected_endpoint_with_garbage_token_is_401(client):
    r = await client.get("/workspaces/", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


async def test_signup_duplicate_email_rejected(client):
    await signup_and_login(client, email="dupe@example.com")
    r = await client.post("/auth/signup", json={"email": "dupe@example.com", "password": "another-pass"})
    assert r.status_code == 400


async def test_login_wrong_password_rejected(client):
    await signup_and_login(client, email="wrongpass@example.com", password="correct-horse")
    r = await client.post("/auth/login", data={"username": "wrongpass@example.com", "password": "incorrect"})
    assert r.status_code == 401


async def test_token_with_no_sub_claim_is_401(client):
    # Validly signed, but create_access_token was never given a "sub"
    # (email) — get_current_user must reject this rather than crashing
    # on `payload.get("sub")` being None.
    token = create_access_token(data={"not_sub": "whatever"})
    r = await client.get("/workspaces/", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_token_for_a_since_deleted_user_is_401(client):
    # Validly signed with a real-looking "sub", but no such user exists
    # in the DB — a token minted for a user who no longer exists.
    token = create_access_token(data={"sub": "ghost@example.com"})
    r = await client.get("/workspaces/", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
