from app.tests.conftest import SAMPLE_CSV, SAMPLE_CSV_V2


async def test_submit_bulk_upload_and_poll_job(client, authed):
    files = [
        ("files", ("a.csv", SAMPLE_CSV, "text/csv")),
        ("files", ("b.csv", SAMPLE_CSV_V2, "text/csv")),
    ]
    r = await client.post("/bulk-upload", headers=authed["headers"], files=files)
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    # CELERY_TASK_ALWAYS_EAGER runs process_bulk_upload_task inline.
    r = await client.get(f"/bulk-upload/{job_id}", headers=authed["headers"])
    assert r.status_code == 200
    job = r.json()
    assert job["status"] == "completed"
    assert job["succeeded"] == 2
    assert job["failed"] == 0


async def test_bulk_upload_all_files_fail_yields_failed_status(client, authed):
    # Passes the (deliberately lenient) upfront content-type check —
    # .csv / text/csv — but fails for real once actually parsed: an
    # empty body raises pandas' EmptyDataError, exactly the "garbage
    # content, clean CSV filename" case that check is documented as NOT
    # catching on its own.
    files = [("files", ("empty.csv", b"", "text/csv"))]
    r = await client.post("/bulk-upload", headers=authed["headers"], files=files)
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    r = await client.get(f"/bulk-upload/{job_id}", headers=authed["headers"])
    job = r.json()
    assert job["status"] == "failed"
    assert job["succeeded"] == 0
    assert job["failed"] == 1


async def test_bulk_upload_no_files_rejected(client, authed):
    r = await client.post("/bulk-upload", headers=authed["headers"], files=[])
    assert r.status_code in (400, 422)


async def test_bulk_upload_job_requires_ownership(client, authed, other_authed):
    files = [("files", ("a.csv", SAMPLE_CSV, "text/csv"))]
    r = await client.post("/bulk-upload", headers=authed["headers"], files=files)
    job_id = r.json()["job_id"]

    r = await client.get(f"/bulk-upload/{job_id}", headers=other_authed["headers"])
    assert r.status_code == 403


async def test_bulk_upload_requires_auth(client):
    r = await client.post("/bulk-upload", files=[("files", ("a.csv", SAMPLE_CSV, "text/csv"))])
    assert r.status_code == 401
