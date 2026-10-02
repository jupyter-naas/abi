"""Execute competency SPARQL for profile modals."""

from __future__ import annotations

import pytest
from naas_abi_marketplace.domains.personnel.apps.people.scripts.sparql_execute import (
    CONTACT_VARIABLES,
    execute_profile_query,
)


def test_profile_header_query_returns_one_row_for_demo_person() -> None:
    result = execute_profile_query("find_profile_header", "alice_dupont", max_rows=10)
    assert result["row_count"] >= 1
    assert "slug" in result["columns"]
    assert any(row[result["columns"].index("slug")] == "alice_dupont" for row in result["rows"])


def test_certifications_query_runs_for_demo_person() -> None:
    result = execute_profile_query("find_certifications", "alice_dupont", max_rows=10)
    assert result["row_count"] >= 1
    assert "certificationName" in result["columns"]


def test_the_header_query_carries_contact_details() -> None:
    result = execute_profile_query("find_profile_header", "alice_dupont", max_rows=1)
    row = dict(zip(result["columns"], result["rows"][0]))
    assert row["emailAddress"] == "alice.dupont@demo.example"
    assert row["telephoneNumber"] == "+33 1 99 00 00 01"
    assert row["linkedinUrl"] == "https://www.linkedin.com/in/alice-dupont-demo"


def test_contact_columns_can_be_withheld() -> None:
    result = execute_profile_query(
        "find_profile_header",
        "alice_dupont",
        max_rows=1,
        hidden_columns=CONTACT_VARIABLES,
    )
    assert not set(result["columns"]) & set(CONTACT_VARIABLES)
    assert "slug" in result["columns"]


def test_unknown_query_is_rejected() -> None:
    with pytest.raises(KeyError):
        execute_profile_query("find_active_employees", "alice_dupont")
