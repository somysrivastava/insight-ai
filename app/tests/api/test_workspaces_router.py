async def test_list_workspaces_returns_own_default_workspace(client, authed):
    r = await client.get("/workspaces/", headers=authed["headers"])
    assert r.status_code == 200
    workspaces = r.json()
    assert len(workspaces) == 1
    assert workspaces[0]["name"] == "Default"


async def test_workspaces_scoped_per_user(client, authed, other_authed):
    r = await client.get("/workspaces/", headers=authed["headers"])
    mine = {w["id"] for w in r.json()}
    r = await client.get("/workspaces/", headers=other_authed["headers"])
    theirs = {w["id"] for w in r.json()}
    assert mine.isdisjoint(theirs)


async def test_workspaces_require_auth(client):
    r = await client.get("/workspaces/")
    assert r.status_code == 401
