"""The login fields of ``tenant:``, checked on both configuration models."""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from naas_abi import NexusConfig, nexus_settings_kwargs
from naas_abi import TenantConfig as ModuleTenantConfig
from naas_abi.apps.nexus.apps.api.app.core.config import Settings
from naas_abi.apps.nexus.apps.api.app.core.config import (
    TenantConfig as NexusTenantConfig,
)
from naas_abi.apps.nexus.tenant_login_config import TenantLoginConfig
from pydantic import BaseModel, ValidationError

BOTH_MODELS = pytest.mark.parametrize(
    "model", [ModuleTenantConfig, NexusTenantConfig], ids=["module", "nexus"]
)

ACME = {
    "login_heading": "Acme Platform",
    "logo_height": 96,
    "login_footer_text": "Acme Research operates this platform.",
    "login_footer_link_label": "Grant 123",
    "login_footer_link_url": "https://example.org/grant/123",
}


def test_the_fields_are_defined_once_for_both_models() -> None:
    assert issubclass(ModuleTenantConfig, TenantLoginConfig)
    assert issubclass(NexusTenantConfig, TenantLoginConfig)
    for name in TenantLoginConfig.model_fields:
        assert name not in inspect.get_annotations(ModuleTenantConfig)
        assert name not in inspect.get_annotations(NexusTenantConfig)


@BOTH_MODELS
def test_unset_keeps_the_typewriter_a_48px_logo_and_no_link(
    model: type[BaseModel],
) -> None:
    tenant: Any = model()
    assert (
        tenant.login_heading,
        tenant.logo_height,
        tenant.login_footer_link_label,
        tenant.login_footer_link_url,
    ) == (None, 48, None, None)


@BOTH_MODELS
def test_valid_values_are_accepted(model: type[BaseModel]) -> None:
    tenant: Any = model(**ACME)
    assert (
        tenant.login_heading,
        tenant.logo_height,
        tenant.login_footer_link_label,
        tenant.login_footer_link_url,
    ) == ("Acme Platform", 96, "Grant 123", "https://example.org/grant/123")


@BOTH_MODELS
@pytest.mark.parametrize("height", [16, 256])
def test_the_logo_height_bounds_are_accepted(
    model: type[BaseModel], height: int
) -> None:
    tenant: Any = model(logo_height=height)
    assert tenant.logo_height == height


@BOTH_MODELS
@pytest.mark.parametrize("url", ["http://example.org", "https://example.org/a?b=c"])
def test_http_and_https_links_are_accepted(model: type[BaseModel], url: str) -> None:
    tenant: Any = model(login_footer_link_label="About", login_footer_link_url=url)
    assert tenant.login_footer_link_url == url


@BOTH_MODELS
@pytest.mark.parametrize("height", [0, -1, 15, 257, 300, 5000])
def test_a_logo_height_out_of_range_is_refused(
    model: type[BaseModel], height: int
) -> None:
    with pytest.raises(ValidationError, match="tenant.logo_height is 16 to 256"):
        model(logo_height=height)


@BOTH_MODELS
@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "ftp://x",
        "/about",
        "about",
        "//example.org/about",
        "https://",
        "https://exa mple.org",
        "https://[::1",
        "https://example.org:abc/",
    ],
)
def test_a_footer_link_that_is_not_an_absolute_http_url_is_refused(
    model: type[BaseModel], url: str
) -> None:
    with pytest.raises(ValidationError, match="tenant.login_footer_link_url is"):
        model(login_footer_link_label="About", login_footer_link_url=url)


@BOTH_MODELS
@pytest.mark.parametrize(
    "fields",
    [
        {"login_footer_link_label": "Grant 123"},
        {"login_footer_link_url": "https://example.org/grant/123"},
        {"login_footer_link_label": "Grant 123", "login_footer_link_url": "  "},
        {"login_footer_link_label": "", "login_footer_link_url": "https://example.org"},
    ],
    ids=["label-only", "url-only", "blank-url", "blank-label"],
)
def test_a_footer_link_label_and_url_are_set_together(
    model: type[BaseModel], fields: dict[str, str]
) -> None:
    with pytest.raises(
        ValidationError,
        match="tenant.login_footer_link_label and tenant.login_footer_link_url",
    ):
        model(**fields)


@BOTH_MODELS
def test_blank_strings_count_as_unset(model: type[BaseModel]) -> None:
    tenant: Any = model(
        login_heading="  ", login_footer_link_label="", login_footer_link_url=" "
    )
    assert (
        tenant.login_heading,
        tenant.login_footer_link_label,
        tenant.login_footer_link_url,
    ) == (None, None, None)


def test_the_login_fields_survive_the_trip_into_nexus_settings() -> None:
    """``tenant:`` in config.yaml reaches the Nexus ``Settings`` through
    ``NexusConfig``: both models refuse extra keys, so walking the actual route
    is what catches a field declared on one side only."""
    settings = Settings(**nexus_settings_kwargs(NexusConfig(tenant=ACME)))

    assert settings.tenant.login_heading == "Acme Platform"
    assert settings.tenant.logo_height == 96
    assert settings.tenant.login_footer_link_label == "Grant 123"
    assert settings.tenant.login_footer_link_url == "https://example.org/grant/123"
