from naas_abi_marketplace.applications.yahoofinance.integrations.YahooFinanceScreenerIntegration import (
    INCLUDE_FIELDS,
    INDUSTRIES,
    REGIONS,
    REQUIRE_POSITIVE_FIELDS,
    SECTORS,
    build_payload,
    taxonomy,
)


def test_build_payload_uses_selected_fields_and_regions():
    payload = build_payload(
        size=100,
        offset=25,
        sector="Technology",
        industry="Software—Infrastructure",
        sort_type="desc",
        sort_field="ebitda.lasttwelvemonths",
        min_revenue=0,
        include_fields=["ticker", "ebitda.lasttwelvemonths"],
        regions=["us", "fr"],
        require_positive=False,
    )

    assert payload["size"] == 100
    assert payload["offset"] == 25
    assert payload["sortType"] == "DESC"
    assert payload["sortField"] == "ebitda.lasttwelvemonths"
    assert payload["includeFields"] == ["ticker", "ebitda.lasttwelvemonths"]
    operands = payload["query"]["operands"]
    assert operands[0]["operands"] == [
        {"operator": "eq", "operands": ["region", "us"]},
        {"operator": "eq", "operands": ["region", "fr"]},
    ]
    assert operands[1]["operands"][0]["operands"] == ["sector", "Technology"]
    assert operands[2]["operands"][0]["operands"] == [
        "industry",
        "Software—Infrastructure",
    ]
    assert operands[3]["operands"][0]["operands"] == [
        "totalrevenues.lasttwelvemonths",
        0,
    ]


def test_build_payload_defaults_cover_full_include_set():
    payload = build_payload(size=25, offset=0)
    assert payload["includeFields"] == INCLUDE_FIELDS
    assert "basicepscontinuingoperations.lasttwelvemonths" in payload["includeFields"]
    regions = [
        item["operands"][1] for item in payload["query"]["operands"][0]["operands"]
    ]
    assert regions == REGIONS
    sectors = [
        item["operands"][1] for item in payload["query"]["operands"][1]["operands"]
    ]
    industries = [
        item["operands"][1] for item in payload["query"]["operands"][2]["operands"]
    ]
    assert sectors == SECTORS
    assert industries == INDUSTRIES
    assert taxonomy()["industries"] == INDUSTRIES
    assert "Software—Infrastructure" in INDUSTRIES
    assert "Waste Management" in INDUSTRIES
    positive = [
        operand["operands"][0]["operands"]
        for operand in payload["query"]["operands"]
        if operand["operands"] and operand["operands"][0].get("operator") == "gt"
    ]
    assert positive == [[field, 0] for field in REQUIRE_POSITIVE_FIELDS]
    assert ["ebitda.lasttwelvemonths", 0] in positive
    assert ["basicepscontinuingoperations.lasttwelvemonths", 0] in positive
