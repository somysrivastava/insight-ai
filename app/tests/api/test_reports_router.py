from app.tests.conftest import upload_sample_dataset


async def test_kpis(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/report/{dataset['id']}/kpis", headers=authed["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["kpis"]["total_records"] == 6


async def test_executive_summary(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/report/{dataset['id']}/summary", headers=authed["headers"])
    assert r.status_code == 200, r.text


async def test_full_report(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/report/{dataset['id']}", headers=authed["headers"])
    assert r.status_code == 200, r.text


async def test_reports_require_ownership(client, authed, other_authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/report/{dataset['id']}/kpis", headers=other_authed["headers"])
    assert r.status_code == 403


async def test_reports_require_auth(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/report/{dataset['id']}/kpis")
    assert r.status_code == 401
