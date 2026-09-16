from app.tests.conftest import SAMPLE_CSV_V2, upload_sample_dataset


async def _create_rule(client, headers, dataset_id, **overrides):
    payload = {
        "name": "Revenue spike",
        "dataset_id": dataset_id,
        "column": "revenue",
        "metric": "sum",
        "condition": "gt",
        "threshold": 5000,
        "frequency": "on_upload",
        "recipients": ["ops@example.com"],
    }
    payload.update(overrides)
    r = await client.post("/alerts", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def test_rule_triggers_on_version_push_and_sends_email(client, authed, sendgrid_mock):
    dataset = await upload_sample_dataset(client, authed["headers"])
    rule = await _create_rule(client, authed["headers"], dataset["id"])

    # SAMPLE_CSV_V2's revenue sum (1400+1010+4700 = 7110) exceeds the
    # threshold (5000) — pushing it should fire the rule via the same
    # check_dataset_alerts_task a fresh upload uses (ADR-015's Day 20
    # on_upload gap).
    files = {"file": ("sales.csv", SAMPLE_CSV_V2, "text/csv")}
    r = await client.post(f"/datasets/{dataset['id']}/versions", headers=authed["headers"], files=files)
    assert r.status_code == 201

    r = await client.get(f"/alerts/{rule['id']}/history", headers=authed["headers"])
    assert r.status_code == 200
    history = r.json()
    assert len(history) == 1
    assert history[0]["triggered"] is True
    assert history[0]["actual_value"] == 7110.0
    assert history[0]["email_sent"] is True
    sendgrid_mock.send.assert_called_once()


async def test_rule_does_not_trigger_when_condition_not_met(client, authed, sendgrid_mock):
    dataset = await upload_sample_dataset(client, authed["headers"])
    rule = await _create_rule(client, authed["headers"], dataset["id"], threshold=100_000)

    files = {"file": ("sales.csv", SAMPLE_CSV_V2, "text/csv")}
    await client.post(f"/datasets/{dataset['id']}/versions", headers=authed["headers"], files=files)

    r = await client.get(f"/alerts/{rule['id']}/history", headers=authed["headers"])
    history = r.json()
    assert history[0]["triggered"] is False
    assert history[0]["email_sent"] is False
    sendgrid_mock.send.assert_not_called()


async def test_daily_frequency_rule_not_triggered_by_upload(client, authed, sendgrid_mock):
    dataset = await upload_sample_dataset(client, authed["headers"])
    rule = await _create_rule(client, authed["headers"], dataset["id"], frequency="daily")

    files = {"file": ("sales.csv", SAMPLE_CSV_V2, "text/csv")}
    await client.post(f"/datasets/{dataset['id']}/versions", headers=authed["headers"], files=files)

    r = await client.get(f"/alerts/{rule['id']}/history", headers=authed["headers"])
    assert r.json() == []  # a daily-only rule isn't checked by an on_upload trigger


async def test_manual_check_endpoint_triggers_immediately(client, authed, sendgrid_mock):
    dataset = await upload_sample_dataset(client, authed["headers"])  # revenue sum 14261.5, well above 5000
    rule = await _create_rule(client, authed["headers"], dataset["id"])

    r = await client.post(f"/alerts/{rule['id']}/check", headers=authed["headers"])
    assert r.status_code == 202

    r = await client.get(f"/alerts/{rule['id']}/history", headers=authed["headers"])
    history = r.json()
    assert len(history) == 1
    assert history[0]["triggered"] is True


async def test_create_rule_rejects_unknown_column(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.post(
        "/alerts",
        headers=authed["headers"],
        json={
            "name": "Bad column",
            "dataset_id": dataset["id"],
            "column": "not_a_real_column",
            "metric": "sum",
            "condition": "gt",
            "threshold": 1,
            "frequency": "on_upload",
            "recipients": ["ops@example.com"],
        },
    )
    assert r.status_code == 400


async def test_alerts_require_ownership(client, authed, other_authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    rule = await _create_rule(client, authed["headers"], dataset["id"])
    r = await client.get(f"/alerts/{rule['id']}", headers=other_authed["headers"])
    assert r.status_code == 403
