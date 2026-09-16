from app.tests.conftest import upload_sample_dataset


async def _create_dashboard(client, headers, name="Sales Overview"):
    r = await client.post("/dashboards", headers=headers, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_list_and_get_dashboard(client, authed):
    dashboard = await _create_dashboard(client, authed["headers"])
    r = await client.get("/dashboards", headers=authed["headers"])
    assert len(r.json()) == 1

    r = await client.get(f"/dashboards/{dashboard['id']}", headers=authed["headers"])
    assert r.status_code == 200
    assert r.json()["pins"] == []


async def test_add_pin_runs_immediately_and_caches_result(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    dashboard = await _create_dashboard(client, authed["headers"])

    r = await client.post(
        f"/dashboards/{dashboard['id']}/pins",
        headers=authed["headers"],
        json={
            "title": "Quick insights",
            "pin_type": "analytics",
            "source_id": dataset["id"],
            "query_params": {"operation": "insights"},
        },
    )
    assert r.status_code == 201, r.text
    pin = r.json()
    assert pin["cached_result"] is not None
    assert pin["last_refreshed_at"] is not None


async def test_add_pin_fails_loudly_for_a_bad_query(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    dashboard = await _create_dashboard(client, authed["headers"])

    r = await client.post(
        f"/dashboards/{dashboard['id']}/pins",
        headers=authed["headers"],
        json={"title": "Broken", "pin_type": "analytics", "source_id": dataset["id"], "query_params": {}},
    )
    assert r.status_code == 400  # missing "operation" -> ValueError -> 400, pin never saved

    r = await client.get(f"/dashboards/{dashboard['id']}", headers=authed["headers"])
    assert r.json()["pins"] == []


async def test_pin_on_dataset_from_another_workspace_rejected(client, authed, other_authed):
    theirs = await upload_sample_dataset(client, other_authed["headers"])
    dashboard = await _create_dashboard(client, authed["headers"])

    r = await client.post(
        f"/dashboards/{dashboard['id']}/pins",
        headers=authed["headers"],
        json={
            "title": "Cross-workspace",
            "pin_type": "analytics",
            "source_id": theirs["id"],
            "query_params": {"operation": "insights"},
        },
    )
    assert r.status_code == 403


async def test_dashboard_requires_ownership(client, authed, other_authed):
    dashboard = await _create_dashboard(client, authed["headers"])
    r = await client.get(f"/dashboards/{dashboard['id']}", headers=other_authed["headers"])
    assert r.status_code == 403


async def test_dashboards_require_auth(client):
    r = await client.get("/dashboards")
    assert r.status_code == 401
