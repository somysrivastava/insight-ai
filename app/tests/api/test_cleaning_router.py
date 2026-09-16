from app.tests.conftest import upload_sample_dataset


async def test_quality_report(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/quality", headers=authed["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dataset_id"] == dataset["id"]


async def test_clean_dataset(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.post(f"/datasets/{dataset['id']}/clean", headers=authed["headers"], json={})
    assert r.status_code == 200, r.text


async def test_quality_report_requires_ownership(client, authed, other_authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/quality", headers=other_authed["headers"])
    assert r.status_code == 403


async def test_quality_report_requires_auth(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/quality")
    assert r.status_code == 401
