"""Platform settings › Access › Features: "Platform access", what the platform offers its
organizations (ADR ``20261127_platform_offer``). Every known feature is listed there; an
organization's page lists those the platform offers; a feature it does not offer is
usable by nobody. Made from ``enabled_features``, which decide alone until it exists."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
    KNOWN_FEATURE_KEYS,
    PINNED_FEATURES,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.adapters.secondary.postgres import (  # noqa: E501
    SqlFeaturePolicyStore,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.port import FeatureChange
from naas_abi.apps.nexus.apps.api.app.services.feature_access.runtime import _features
from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import (
    FeatureAccessService,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.service_test import FEATURES
from naas_abi.apps.nexus.apps.api.app.services.iam import platform_offer
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ, feature_exists
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    CONTAINER_DEFAULTS,
    ensure_platform_offer,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import PLATFORM, org_container
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import offer_of
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError

EVERY = [key for key in KNOWN_FEATURE_KEYS if key not in PINNED_FEATURES]


@pytest.fixture
def service(nexus_db, audit) -> FeatureAccessService:
    """The service as the engine builds it: the features an offer switches are those the
    platform offers (``runtime._features``)."""
    return FeatureAccessService(
        EngineIamGateway(),
        SqlFeaturePolicyStore(nexus_db),
        audit,
        container_of=AUTHZ.container_of,
        defaults_of=CONTAINER_DEFAULTS.record_of,
        features=_features,
    )


def _keys(state: dict) -> list[str]:
    return [row["key"] for row in state["features"]]


def _choices(state: dict) -> dict[str, str]:
    return {row["key"]: row["choice"] for row in state["features"]}


def _make(nexus) -> str:
    with as_service_account("api"):
        made = ensure_platform_offer(nexus.iam)
    platform_offer.forget()
    return made


@pytest.mark.asyncio
async def test_until_platform_access_is_made_enabled_features_decide(nexus, acme, service):
    assert platform_offer.offered() is None
    assert feature_exists("chat") and not feature_exists("sheets")
    with pytest.raises(IAMNotFoundError):
        await service.read("root", PLATFORM)


@pytest.mark.asyncio
async def test_it_is_made_once_from_enabled_features(nexus, acme, service):
    first = _make(nexus)
    assert _make(nexus) == first
    with as_service_account("api"):
        assert offer_of(nexus.iam.get_policy(first).document).features == set(FEATURES)
    assert platform_offer.offered() == frozenset(FEATURES)


@pytest.mark.asyncio
async def test_the_platform_lists_every_feature_and_offers_its_organizations_those_it_picks(
    nexus, acme, service
):
    _make(nexus)
    state = await service.read("root", PLATFORM)
    assert _keys(state) == EVERY
    assert _choices(state)["chat"] == "everyone" and _choices(state)["sheets"] == "nobody"
    assert state["policies"] == [state["access_policy"]]
    # An organization's page lists what the platform offers, nothing else.
    org = org_container("acme")
    assert "sheets" not in _keys(await service.read("root", org))

    state = await service.save("root", PLATFORM, [FeatureChange("sheets", "everyone", ())])
    assert not state["errors"] and _choices(state)["sheets"] == "everyone"
    assert feature_exists("sheets")
    assert "sheets" in _keys(await service.read("root", org))

    # Taken back from the platform: usable by nobody, listed by no organization.
    await service.save("root", PLATFORM, [FeatureChange("chat", "nobody", ())])
    assert not feature_exists("chat")
    assert "chat" not in _keys(await service.read("root", org))


@pytest.mark.asyncio
async def test_a_workspace_admin_does_not_change_what_the_platform_offers(nexus, acme, service):
    _make(nexus)
    state = await service.save("olivia", PLATFORM, [FeatureChange("sheets", "everyone", ())])
    assert state["errors"].get("sheets")
    assert not feature_exists("sheets")
