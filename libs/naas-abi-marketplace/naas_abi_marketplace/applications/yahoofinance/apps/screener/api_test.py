import json

from fastapi.testclient import TestClient
from naas_abi_marketplace.applications.yahoofinance.apps.screener import (
    api as screener_api,
)
from naas_abi_marketplace.applications.yahoofinance.apps.screener.api import (
    flatten_organization,
    rows_for_view,
)
from naas_abi_marketplace.applications.yahoofinance.apps.screener.schema import (
    parse_company_list,
    row_matches_company_list,
)
from naas_abi_marketplace.applications.yahoofinance.apps.screener.serve import (
    create_app,
)
from naas_abi_marketplace.applications.yahoofinance.integrations.utils.DedupScreenerOrgs import (
    dedup_records,
)


def test_schema_and_payload_preview():
    client = TestClient(create_app())
    schema = client.get("/api/yahoofinance/screener/schema")
    assert schema.status_code == 200
    body = schema.json()
    assert "ticker" in body["includeFields"]
    assert body["defaults"]["industry"] == "Software—Infrastructure"
    ovh_peers = next(item for item in body["watchlists"] if item["id"] == "ovh-peers")
    assert "OVH.PA" in ovh_peers["tokens"]
    assert "DOCN" in ovh_peers["tokens"]

    preview = client.post(
        "/api/yahoofinance/screener/payload",
        json={
            "size": 100,
            "sector": "Technology",
            "industry": "Software—Infrastructure",
            "include_fields": ["ticker", "companyshortname"],
            "regions": ["fr", "us"],
            "sort_field": "ebitda.lasttwelvemonths",
        },
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["query"]["useRecordsResponse"] is True
    assert payload["body"]["includeFields"] == ["ticker", "companyshortname"]
    assert payload["body"]["sortField"] == "ebitda.lasttwelvemonths"


def test_snapshot_path_is_restricted(monkeypatch, tmp_path):
    snapshot = tmp_path / "Technology" / "example.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text(
        json.dumps(
            {
                "finance": {
                    "result": [
                        {
                            "start": 0,
                            "count": 1,
                            "total": 1,
                            "records": [
                                {
                                    "ticker": "OVH.PA",
                                    "companyName": "OVH Groupe",
                                    "marketCap": {"raw": 1, "fmt": "1"},
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(screener_api, "DATA_DIR", tmp_path)
    client = TestClient(create_app())

    listed = client.get("/api/yahoofinance/screener/snapshots")
    assert listed.status_code == 200
    assert listed.json()["snapshots"][0]["id"] == "Technology/example.json"

    loaded = client.get(
        "/api/yahoofinance/screener/snapshot",
        params={"id": "Technology/example.json"},
    )
    assert loaded.status_code == 200
    assert loaded.json()["rows"][0]["ticker"] == "OVH.PA"

    traversal = client.get(
        "/api/yahoofinance/screener/snapshot",
        params={"id": "../example.json"},
    )
    assert traversal.status_code == 400


def test_rows_for_view_flattens_primary_listing():
    records = [
        {
            "companyName": "OVH Groupe S.A.",
            "ticker": "OVH.PA",
            "sector": "Technology",
            "industry": "Software—Infrastructure",
            "region": "fr",
            "avgDailyVol3m": {"raw": 130159},
            "marketCap": {"raw": 2_431_000_000},
            "ebitdaLtm": {"raw": 304_800_000},
        },
        {
            "companyName": "OVH Groupe Société anonyme",
            "ticker": "7U7.DU",
            "sector": "Technology",
            "industry": "Software—Infrastructure",
            "region": "de",
            "avgDailyVol3m": {"raw": 23},
            "marketCap": {"raw": 3_836_000_000},
        },
    ]
    payload = {"finance": {"result": [{"records": records, "total": 2, "start": 0}]}}
    listings = rows_for_view(payload, "listings")
    orgs = rows_for_view(payload, "organizations")
    assert len(listings) == 2
    assert len(orgs) == 1
    row = orgs[0]
    assert row["ticker"] == "OVH.PA"
    assert row["listingCount"] == 2
    assert "OVH.PA" in row["stockIds"]
    assert row["ebitdaLtm"]["raw"] == 304_800_000
    flattened = flatten_organization(dedup_records(records)[0])
    assert flattened["primaryTicker"] == "OVH.PA"


def test_company_list_matches_ovh_peers_but_not_oracle_japan():
    tokens = parse_company_list("OVH.PA, DOCN, ORCL, DigitalOcean")
    assert row_matches_company_list(
        {"ticker": "OVH.PA", "companyName": "OVH Groupe S.A."}, tokens
    )
    assert row_matches_company_list(
        {"ticker": "7U7.F", "companyName": "OVH Groupe S.A."},
        parse_company_list("OVH"),
    )
    assert row_matches_company_list(
        {"ticker": "DOCN", "companyName": "DigitalOcean Holdings, Inc."}, tokens
    )
    assert row_matches_company_list(
        {"ticker": "ORCL.VI", "companyName": "Oracle Corporation"}, tokens
    )
    assert not row_matches_company_list(
        {
            "ticker": "4716.T",
            "companyName": "Oracle Corporation Japan",
        },
        tokens,
    )
