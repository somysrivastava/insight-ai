from app.tests.conftest import fake_chat_completion, upload_sample_dataset


async def test_bulk_upsert_then_get_dictionary(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    payload = {
        "mappings": [
            {"column_name": "revenue", "display_name": "Revenue ($)", "unit": "USD", "is_metric": True},
        ]
    }
    r = await client.put(f"/datasets/{dataset['id']}/dictionary", headers=authed["headers"], json=payload)
    assert r.status_code == 200, r.text
    assert r.json()[0]["display_name"] == "Revenue ($)"

    r = await client.get(f"/datasets/{dataset['id']}/dictionary", headers=authed["headers"])
    assert len(r.json()) == 1


async def test_patch_updates_existing_mapping(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    await client.put(
        f"/datasets/{dataset['id']}/dictionary",
        headers=authed["headers"],
        json={"mappings": [{"column_name": "revenue", "display_name": "Revenue"}]},
    )
    r = await client.patch(
        f"/datasets/{dataset['id']}/dictionary/revenue", headers=authed["headers"], json={"unit": "USD"}
    )
    assert r.status_code == 200
    assert r.json()["unit"] == "USD"
    assert r.json()["display_name"] == "Revenue"  # untouched by the PATCH


async def test_delete_mapping(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    await client.put(
        f"/datasets/{dataset['id']}/dictionary",
        headers=authed["headers"],
        json={"mappings": [{"column_name": "revenue", "display_name": "Revenue"}]},
    )
    r = await client.delete(f"/datasets/{dataset['id']}/dictionary/revenue", headers=authed["headers"])
    assert r.status_code == 204
    r = await client.get(f"/datasets/{dataset['id']}/dictionary", headers=authed["headers"])
    assert r.json() == []


async def test_suggest_never_sends_raw_cell_values_and_saves_suggestions(client, authed, openai_mock):
    dataset = await upload_sample_dataset(client, authed["headers"])
    openai_mock.chat.completions.create.return_value = fake_chat_completion(
        {
            "suggestions": [
                {"column_name": "revenue", "display_name": "Revenue", "description": "Order revenue", "unit": "USD"},
            ]
        }
    )
    r = await client.post(f"/datasets/{dataset['id']}/dictionary/suggest", headers=authed["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["suggested"][0]["column_name"] == "revenue"

    # ADR-009: only column names/dtypes/stats go to the model — never a
    # raw cell value from the actual data (e.g. "West", "Widget").
    sent_content = openai_mock.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "West" not in sent_content
    assert "Widget" not in sent_content


async def test_dictionary_requires_ownership(client, authed, other_authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/dictionary", headers=other_authed["headers"])
    assert r.status_code == 403


async def test_dictionary_requires_auth(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/dictionary")
    assert r.status_code == 401
