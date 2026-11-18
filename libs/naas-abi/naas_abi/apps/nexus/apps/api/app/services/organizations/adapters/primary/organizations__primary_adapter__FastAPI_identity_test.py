from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary.organizations__primary_adapter__FastAPI import (  # noqa: E501
    ORGANIZATION_IDENTITY_FIELDS,
    Organization,
    OrganizationBranding,
    OrganizationCreate,
    OrganizationUpdate,
)
from pydantic import ValidationError


def test_the_identity_is_part_of_the_organization_not_of_its_public_branding() -> None:
    for field in ORGANIZATION_IDENTITY_FIELDS:
        assert field in Organization.model_fields
        assert field not in OrganizationBranding.model_fields
        assert field in OrganizationUpdate.model_fields
        assert field in OrganizationCreate.model_fields


def test_a_blank_value_clears_a_field() -> None:
    update = OrganizationUpdate(legal_name="  ", city="")
    assert update.model_dump(exclude_unset=True) == {"legal_name": None, "city": None}


def test_values_are_trimmed() -> None:
    assert OrganizationUpdate(city="  Paris ").city == "Paris"


@pytest.mark.parametrize("url", ["https://acme.example", "http://localhost:3000/about"])
def test_a_website_is_an_http_or_https_url(url: str) -> None:
    assert OrganizationUpdate(website=url).website == url


@pytest.mark.parametrize(
    "url", ["acme.example", "javascript:alert(1)", "ftp://acme.example", "https://"]
)
def test_anything_else_is_refused(url: str) -> None:
    with pytest.raises(ValidationError, match="website"):
        OrganizationUpdate(website=url)


def test_the_contact_email_is_an_address_kept_in_lower_case() -> None:
    assert OrganizationUpdate(contact_email="Hello@Acme.Example").contact_email == (
        "hello@acme.example"
    )
    with pytest.raises(ValidationError, match="contact_email"):
        OrganizationUpdate(contact_email="not an address")


def test_lengths_are_bounded() -> None:
    with pytest.raises(ValidationError):
        OrganizationUpdate(postal_code="1" * 21)


def test_a_new_organization_takes_its_identity_with_the_same_rules() -> None:
    org = OrganizationCreate(
        name="Acme",
        slug="acme",
        legal_name=" Acme Holding SAS ",
        website="https://acme.example",
        contact_email="Hello@Acme.Example",
        city="",
    )
    assert (org.legal_name, org.contact_email, org.city) == (
        "Acme Holding SAS",
        "hello@acme.example",
        None,
    )
    with pytest.raises(ValidationError, match="website"):
        OrganizationCreate(name="Acme", slug="acme", website="acme.example")
