from naas_abi_marketplace.applications.yahoofinance.integrations.utils.DedupScreenerOrgs import (
    dedup_records,
    organization_key,
)


def test_organization_key_strips_legal_form_variants():
    assert organization_key("OVH Groupe S.A.", "OVH.PA") == organization_key(
        "OVH Groupe Société anonyme", "7U7.DU"
    )
    assert organization_key("Oracle Corporation", "ORCL") != organization_key(
        "Oracle Corporation Japan", "4716.T"
    )


def test_dedup_records_keeps_listing_parameters():
    records = [
        {
            "companyName": "OVH Groupe S.A.",
            "ticker": "OVH.PA",
            "sector": "Technology",
            "industry": "Software—Infrastructure",
            "region": "fr",
            "avgDailyVol3m": {"raw": 130159},
            "marketCap": {"raw": 2_431_000_000},
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

    organizations = dedup_records(records)

    assert len(organizations) == 1
    org = organizations[0]
    assert org["primaryTicker"] == "OVH.PA"
    assert org["listingCount"] == 2
    assert org["parameters"]["stockIds"] == ["OVH.PA", "7U7.DU"]
    listings = org["parameters"]["listings"]
    assert {item["stockId"] for item in listings} == {"OVH.PA", "7U7.DU"}
    assert {item["region"] for item in listings} == {"fr", "de"}
    assert "ticker" in listings[0]
    assert "companyName" not in listings[0]
