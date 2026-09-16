from app.tests.conftest import SAMPLE_CSV, fake_chat_completion, upload_sample_dataset


async def test_upload_then_summary_then_ai_query(client, authed, openai_mock):
    dataset = await upload_sample_dataset(client, authed["headers"])
    assert dataset["rows"] == 6
    assert dataset["columns"] == 5

    r = await client.get(f"/datasets/{dataset['id']}/summary", headers=authed["headers"])
    assert r.status_code == 200
    summary = r.json()
    assert summary["rows"] == 6
    assert set(summary["column_name"]) == {"region", "product", "revenue", "units", "order_date"}

    r = await client.post(
        f"/datasets/{dataset['id']}/query", headers=authed["headers"], json={"question": "What is the total revenue?"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["operation"] == "aggregate"
    # SAMPLE_CSV revenue sum = 1200.50+980.25+4500.00+3100.75+1580.00+2900.00
    assert body["data"]["value"] == 14261.5
    openai_mock.chat.completions.create.assert_called_once()


async def test_ai_query_groupby_shape(client, authed, openai_mock):
    dataset = await upload_sample_dataset(client, authed["headers"])
    openai_mock.chat.completions.create.return_value = fake_chat_completion(
        {
            "operation": "groupby",
            "column": "region",
            "metric": "revenue",
            "aggregate": "sum",
            "filter_value": None,
            "filter_operator": "eq",
            "limit": 0,
            "direction": "asc",
            "explanation": "Revenue grouped by region.",
        }
    )
    r = await client.post(
        f"/datasets/{dataset['id']}/query", headers=authed["headers"], json={"question": "Revenue by region?"}
    )
    assert r.status_code == 200, r.text
    records = r.json()["data"]["records"]
    assert {row["region"] for row in records} == {"East", "West"}


async def test_ai_query_never_hits_real_openai_without_mock(client, authed, monkeypatch):
    """Sanity check on the mocking strategy itself: with no openai_mock
    fixture, _get_client() is unpatched — assert it's never actually
    called by pointing it at something that would blow up loudly if it
    were, rather than silently reaching the network."""

    def _boom():
        raise AssertionError("a test hit the real OpenAI client factory")

    monkeypatch.setattr("app.services.ai_service._get_client", _boom)

    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/summary", headers=authed["headers"])
    assert r.status_code == 200  # summary alone must never touch OpenAI


async def test_summary_requires_ownership(client, authed, other_authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/summary", headers=other_authed["headers"])
    assert r.status_code == 403


async def test_upload_rejects_non_csv_excel_content_type(client, authed):
    # application/octet-stream is deliberately allowed (see
    # dataset_service.py's _ALLOWED_UPLOAD_CONTENT_TYPES comment — real
    # browsers commonly send it for a genuine CSV) — this needs a
    # content type actually outside that allowlist to exercise the
    # rejection.
    files = {"file": ("photo.png", b"\x89PNG fake bytes", "image/png")}
    r = await client.post("/upload", headers=authed["headers"], files=files)
    assert r.status_code == 400
