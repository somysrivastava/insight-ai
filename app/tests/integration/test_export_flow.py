from app.tests.conftest import upload_sample_dataset


async def test_trigger_poll_and_download_csv_export(client, authed, openai_mock):
    dataset = await upload_sample_dataset(client, authed["headers"])

    r = await client.post(
        f"/datasets/{dataset['id']}/export",
        headers=authed["headers"],
        json={"source": "query", "format": "csv", "question": "What is the total revenue?"},
    )
    assert r.status_code == 202, r.text
    task_id = r.json()["task_id"]

    # CELERY_TASK_ALWAYS_EAGER (test env only) runs the task body inline,
    # so the job is already done by the time we poll — no worker
    # container exists in the test stack to do it asynchronously.
    r = await client.get(f"/jobs/{task_id}", headers=authed["headers"])
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["status"] == "success"
    export_id = job["result"]["export_id"]
    assert job["result"]["status"] == "success"

    r = await client.get(f"/exports/{export_id}", headers=authed["headers"])
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert b"revenue" in r.content.lower() or b"value" in r.content.lower()


async def test_export_job_polling_requires_ownership(client, authed, other_authed, openai_mock):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.post(
        f"/datasets/{dataset['id']}/export",
        headers=authed["headers"],
        json={"source": "query", "format": "csv", "question": "total revenue"},
    )
    task_id = r.json()["task_id"]

    r = await client.get(f"/jobs/{task_id}", headers=other_authed["headers"])
    assert r.status_code == 403


async def test_download_export_requires_workspace_membership(client, authed, other_authed, openai_mock):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.post(
        f"/datasets/{dataset['id']}/export",
        headers=authed["headers"],
        json={"source": "query", "format": "csv", "question": "total revenue"},
    )
    task_id = r.json()["task_id"]
    r = await client.get(f"/jobs/{task_id}", headers=authed["headers"])
    export_id = r.json()["result"]["export_id"]

    r = await client.get(f"/exports/{export_id}", headers=other_authed["headers"])
    assert r.status_code == 403


async def test_job_status_404_for_unknown_task_id(client, authed):
    r = await client.get("/jobs/00000000-0000-0000-0000-000000000000", headers=authed["headers"])
    assert r.status_code == 404
