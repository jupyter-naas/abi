"""An organization's time zone (Organization Settings > General): the analytics
periods of the organization and of its workspaces follow it."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary.organizations__primary_adapter__FastAPI import (  # noqa: E501
    Organization,
    OrganizationUpdate,
)
from pydantic import ValidationError


def test_an_organization_is_in_utc_until_set() -> None:
    org = Organization(id="o", name="O", slug="o", owner_id="u")
    assert org.timezone == "UTC"


@pytest.mark.parametrize("name", ["Europe/Paris", "America/New_York", "UTC", "Asia/Kolkata"])
def test_an_iana_time_zone_is_accepted(name: str) -> None:
    assert OrganizationUpdate(timezone=name).model_dump(exclude_unset=True) == {"timezone": name}


@pytest.mark.parametrize("name", ["Mars/Olympus", "CEST+2", "", "../../etc/passwd", None])
def test_anything_else_is_refused(name: str | None) -> None:
    with pytest.raises(ValidationError, match="timezone"):
        OrganizationUpdate(timezone=name)


def test_an_update_without_a_time_zone_keeps_it() -> None:
    assert "timezone" not in OrganizationUpdate(name="New").model_dump(exclude_unset=True)
