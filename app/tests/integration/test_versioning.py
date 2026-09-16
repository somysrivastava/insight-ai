from app.tests.conftest import SAMPLE_CSV_BAD_COLUMNS, SAMPLE_CSV_V2, upload_sample_dataset


async def test_upload_creates_version_1(client, authed, db):
    from app.services.version_service import get_versions

    dataset = await upload_sample_dataset(client, authed["headers"])
    versions = get_versions(db, dataset["id"])
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].is_current is True


async def test_push_version_creates_version_2_and_lists_both(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])

    files = {"file": ("sales.csv", SAMPLE_CSV_V2, "text/csv")}
    r = await client.post(f"/datasets/{dataset['id']}/versions", headers=authed["headers"], files=files)
    assert r.status_code == 201, r.text
    pushed = r.json()
    assert pushed["version_number"] == 2
    assert pushed["is_current"] is True

    r = await client.get(f"/datasets/{dataset['id']}/versions", headers=authed["headers"])
    versions = r.json()
    assert len(versions) == 2
    assert {v["version_number"] for v in versions} == {1, 2}
    current = next(v for v in versions if v["is_current"])
    assert current["version_number"] == 2


async def test_summary_reflects_the_pushed_version(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    files = {"file": ("sales.csv", SAMPLE_CSV_V2, "text/csv")}
    await client.post(f"/datasets/{dataset['id']}/versions", headers=authed["headers"], files=files)

    r = await client.get(f"/datasets/{dataset['id']}/summary", headers=authed["headers"])
    assert r.json()["rows"] == 3  # SAMPLE_CSV_V2 has 3 data rows, SAMPLE_CSV has 6


async def test_push_with_mismatched_columns_rejected(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    files = {"file": ("sales.csv", SAMPLE_CSV_BAD_COLUMNS, "text/csv")}
    r = await client.post(f"/datasets/{dataset['id']}/versions", headers=authed["headers"], files=files)
    assert r.status_code == 400
    assert "columns" in r.json()["detail"].lower()

    # Rejected push must not have created a new version.
    r = await client.get(f"/datasets/{dataset['id']}/versions", headers=authed["headers"])
    assert len(r.json()) == 1


async def test_rollback_creates_a_new_version_not_a_rewind(client, authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    files = {"file": ("sales.csv", SAMPLE_CSV_V2, "text/csv")}
    await client.post(f"/datasets/{dataset['id']}/versions", headers=authed["headers"], files=files)

    r = await client.post(f"/datasets/{dataset['id']}/versions/1/rollback", headers=authed["headers"])
    assert r.status_code == 201, r.text
    rolled_back = r.json()
    assert rolled_back["version_number"] == 3  # not back to 1 — a new, third version
    assert "Rolled back to version 1" in rolled_back["change_summary"]

    r = await client.get(f"/datasets/{dataset['id']}/summary", headers=authed["headers"])
    assert r.json()["rows"] == 6  # back to version 1's row count, via the new version 3


async def test_versions_require_ownership(client, authed, other_authed):
    dataset = await upload_sample_dataset(client, authed["headers"])
    r = await client.get(f"/datasets/{dataset['id']}/versions", headers=other_authed["headers"])
    assert r.status_code == 403
