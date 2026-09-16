from app.tests.conftest import upload_sample_dataset


async def test_bar_chart(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.post(
        f"/datasets/{dataset['id']}/charts/bar",
        headers=authed["headers"],
        json={"category_column": "region", "value_column": "revenue"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["chart_type"] == "bar"
    assert r.json()["row_count"] > 0


async def test_line_chart(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.post(
        f"/datasets/{dataset['id']}/charts/line",
        headers=authed["headers"],
        json={"date_column": "order_date", "value_column": "revenue"},
    )
    assert r.status_code == 200, r.text


async def test_bar_chart_requires_ownership(client, authed, other_authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.post(
        f"/datasets/{dataset['id']}/charts/bar",
        headers=other_authed["headers"],
        json={"category_column": "region", "value_column": "revenue"},
    )
    assert r.status_code == 403


async def test_bar_chart_requires_auth(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.post(
        f"/datasets/{dataset['id']}/charts/bar", json={"category_column": "region", "value_column": "revenue"}
    )
    assert r.status_code == 401
