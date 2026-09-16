from app.tests.conftest import fake_chat_completion, upload_sample_dataset

JOIN_QUERY = {
    "operation": "aggregate",
    "column": None,
    "metric": "orders.revenue",
    "aggregate": "sum",
    "filter_value": None,
    "filter_operator": "eq",
    "limit": 0,
    "direction": "asc",
    "explanation": "Total revenue across the joined result.",
}


async def _two_datasets(client, headers):
    a = await upload_sample_dataset(client, headers, filename="orders.csv")
    b = await upload_sample_dataset(client, headers, filename="orders2.csv")
    return a, b


async def test_create_and_query_join(client, authed, openai_mock):
    a, b = await _two_datasets(client, authed["headers"])
    openai_mock.chat.completions.create.return_value = fake_chat_completion(JOIN_QUERY)

    payload = {
        "name": "orders-join",
        "datasets": [{"id": a["id"], "alias": "orders"}, {"id": b["id"], "alias": "more"}],
        "joins": [
            {
                "left_alias": "orders",
                "right_alias": "more",
                "on": [{"left": "region", "right": "region"}],
                "type": "inner",
            }
        ],
        "question": "What is the total revenue?",
    }
    r = await client.post("/joins", headers=authed["headers"], json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["join_id"] is not None  # named -> saved

    r = await client.get("/joins", headers=authed["headers"])
    assert len(r.json()) == 1


async def test_join_across_datasets_in_different_workspaces_rejected(client, authed, other_authed, openai_mock):
    mine = await upload_sample_dataset(client, authed["headers"])
    theirs = await upload_sample_dataset(client, other_authed["headers"])

    payload = {
        "datasets": [{"id": mine["id"], "alias": "a"}, {"id": theirs["id"], "alias": "b"}],
        "joins": [{"left_alias": "a", "right_alias": "b", "on": [{"left": "region", "right": "region"}], "type": "inner"}],
        "question": "anything",
    }
    # `mine` belongs to `authed`'s workspace; `theirs` doesn't even exist
    # for `authed` to access in the first place — access_control denies
    # it as a 403 before the join logic's own same-workspace check runs.
    r = await client.post("/joins", headers=authed["headers"], json=payload)
    assert r.status_code == 403


async def test_saved_join_requires_ownership(client, authed, other_authed, openai_mock):
    a, b = await _two_datasets(client, authed["headers"])
    openai_mock.chat.completions.create.return_value = fake_chat_completion(JOIN_QUERY)
    payload = {
        "name": "orders-join",
        "datasets": [{"id": a["id"], "alias": "orders"}, {"id": b["id"], "alias": "more"}],
        "joins": [{"left_alias": "orders", "right_alias": "more", "on": [{"left": "region", "right": "region"}], "type": "inner"}],
        "question": "total revenue",
    }
    r = await client.post("/joins", headers=authed["headers"], json=payload)
    join_id = r.json()["join_id"]

    r = await client.get(f"/joins/{join_id}", headers=other_authed["headers"])
    assert r.status_code == 403


async def test_joins_require_auth(client):
    r = await client.get("/joins")
    assert r.status_code == 401
