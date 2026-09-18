"""Execute competency SPARQL for profile modals."""

from __future__ import annotations

import pytest
from naas_abi_marketplace.domains.personnel.apps.people.sparql_execute import (
    execute_profile_query,
)


def test_profile_header_query_returns_one_row_for_demo_person() -> None:
    result = execute_profile_query("find_profile_header", "alice_dupont", max_rows=10)
    assert result["row_count"] >= 1
    assert "slug" in result["columns"]
    assert any(row[result["columns"].index("slug")] == "alice_dupont" for row in result["rows"])


def test_unknown_query_is_rejected() -> None:
    with pytest.raises(KeyError):
        execute_profile_query("find_active_employees", "alice_dupont")
