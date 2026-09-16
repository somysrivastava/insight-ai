from app.tests.conftest import upload_sample_dataset


async def test_insights(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/analytics", headers=authed["headers"])
    assert r.status_code == 200, r.text


async def test_trends(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/trends/", headers=authed["headers"])
    assert r.status_code == 200, r.text


async def test_breakdown_by_region(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/breakdown", headers=authed["headers"], params={"group_by": "region"})
    assert r.status_code == 200, r.text


async def test_breakdown_unknown_column_rejected(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(
        f"/datasets/{dataset['id']}/breakdown", headers=authed["headers"], params={"group_by": "not_a_column"}
    )
    # get_breakdown's except block catches every Exception (including a
    # bad-column ValueError from analytics_service) into a bare 500 —
    # not ideal, but that's the router's real, current behavior.
    assert r.status_code == 500


async def test_analytics_requires_ownership(client, authed, other_authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/analytics", headers=other_authed["headers"])
    assert r.status_code == 403


async def test_analytics_requires_auth(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/analytics")
    assert r.status_code == 401
