from app.tests.conftest import upload_sample_dataset


async def _create_schedule(client, headers, source_id, **overrides):
    payload = {
        "name": "Weekly revenue",
        "source_type": "dataset_query",
        "source_id": source_id,
        "question": "What is the total revenue?",
        "export_format": "csv",
        "frequency": "weekly",
        "day_of_week": 1,
        "hour": 9,
        "recipients": ["ops@example.com"],
    }
    payload.update(overrides)
    r = await client.post("/schedules", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_list_get_schedule(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    schedule = await _create_schedule(client, authed["headers"], dataset["id"])
    assert schedule["next_run_at"]

    r = await client.get("/schedules", headers=authed["headers"])
    assert len(r.json()) == 1

    r = await client.get(f"/schedules/{schedule['id']}", headers=authed["headers"])
    assert r.status_code == 200


async def test_run_schedule_now(client, authed, openai_mock, sendgrid_mock):
    dataset = await upload_sample_dataset(client, authed["headers"])
    schedule = await _create_schedule(client, authed["headers"], dataset["id"])

    r = await client.post(f"/schedules/{schedule['id']}/run", headers=authed["headers"])
    assert r.status_code == 202, r.text
    task_id = r.json()["task_id"]

    r = await client.get(f"/jobs/{task_id}", headers=authed["headers"])
    assert r.json()["status"] == "success"
    sendgrid_mock.send.assert_called_once()


async def test_delete_schedule(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    schedule = await _create_schedule(client, authed["headers"], dataset["id"])
    r = await client.delete(f"/schedules/{schedule['id']}", headers=authed["headers"])
    assert r.status_code == 204
    r = await client.get("/schedules", headers=authed["headers"])
    assert r.json() == []


async def test_weekly_without_day_of_week_rejected(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.post(
        "/schedules",
        headers=authed["headers"],
        json={
            "name": "Bad schedule",
            "source_type": "dataset_query",
            "source_id": dataset["id"],
            "question": "total revenue",
            "export_format": "csv",
            "frequency": "weekly",
            "hour": 9,
            "recipients": ["ops@example.com"],
        },
    )
    assert r.status_code == 422


async def test_schedules_require_ownership(client, authed, other_authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    schedule = await _create_schedule(client, authed["headers"], dataset["id"])
    r = await client.get(f"/schedules/{schedule['id']}", headers=other_authed["headers"])
    assert r.status_code == 403


async def test_schedules_require_auth(client):
    r = await client.get("/schedules")
    assert r.status_code == 401
