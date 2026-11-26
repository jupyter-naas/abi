"""The Maps part of each workspace's offer "<W> access" (``iam/given_maps``), read through
the authorizer's offer cache and written as the caller through the offer service, so IAM's
rules apply to every change: grant only what you hold (a deployment item is the platform
admin's to give, an item of V whoever holds it in V's), a workspace's admin narrows."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import given_maps
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    MapsAssignment,
    MapsPermissionError,
    MapsPermissionValidationError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.port import MapsOfferPort
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError


class IamMapsOffers(MapsOfferPort):
    async def assignment(self, workspace_id: str) -> MapsAssignment | None:
        container = await AUTHZ.container_of(workspace_id)
        offer = await AUTHZ.offer_of(container) if container else None
        return None if offer is None else given_maps.assignment_of(offer)

    async def change(
        self, user: Any, workspace_id: str, kind: str, item_id: str, owner: str, *, given: bool
    ) -> None:
        from naas_abi.apps.nexus.apps.api.app.services.feature_access.runtime import (
            get_feature_access_service,
        )

        owner_container = None
        if owner != DEPLOYMENT:
            owner_container = await AUTHZ.container_of(owner)
            if owner_container is None:
                raise MapsPermissionValidationError([f"unknown workspace {owner!r}"])

        def apply(offer: Any) -> Any:
            fields = given_maps.with_item(
                offer, kind, item_id, owner_container=owner_container, given=given
            )
            return replace(offer, **fields)

        sign = "+" if given else "-"
        try:
            await get_feature_access_service().set_maps(
                user, workspace_id, apply, detail=f"{sign}{kind}:{owner or 'platform'}/{item_id}"
            )
        except IAMNotFoundError as exc:
            # IAM hides a policy from whoever may not read it: not theirs to change.
            raise MapsPermissionError(
                f"IAM does not let you change what {workspace_id} may use"
            ) from exc
