from app.tests.conftest import upload_sample_dataset


async def test_list_datasets_returns_only_own_workspace(client, authed, other_authed):
    await upload_sample_dataset(client, authed["headers"])
    await upload_sample_dataset(client, other_authed["headers"])

    r = await client.get("/datasets/", headers=authed["headers"])
    assert r.status_code == 200
    datasets = r.json()["datasets"]
    assert len(datasets) == 1


async def test_list_datasets_requires_auth(client):
    r = await client.get("/datasets/")
    assert r.status_code == 401


async def test_download_url_not_available_on_local_backend(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/download", headers=authed["headers"])
    # LocalStorageBackend.url_for() always returns None — documented as
    # a 400, not a crash.
    assert r.status_code == 400


async def test_download_url_requires_ownership(client, authed, other_authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/download", headers=other_authed["headers"])
    assert r.status_code == 403


async def test_summary_404_for_nonexistent_dataset(client, authed):
    r = await client.get("/datasets/999999/summary", headers=authed["headers"])
    assert r.status_code == 404


async def test_upload_requires_auth(client):
    files = {"file": ("sales.csv", b"a,b\n1,2\n", "text/csv")}
    r = await client.post("/upload", files=files)
    assert r.status_code == 401
