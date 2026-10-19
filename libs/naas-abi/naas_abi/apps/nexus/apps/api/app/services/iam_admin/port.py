"""What the IAM admin pages need from the engine: IAM itself, as the caller.

The port is IAM's own service interface (``IIAMService``), bound to the signed-in
user: every call is decided by the user's policies, never by Nexus. The few reads
that only name things the caller already holds an id of (the name of a policy, the
profile of a principal in a list) are the engine's own (``lookup``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.IAMPorts import IIAMService, Policy, PrincipalRecord


class IamUnavailableError(RuntimeError):
    """Nexus has no IAM to administer (it runs without the engine's)."""


class IamGateway(ABC):
    @abstractmethod
    def bind(self, user: Any) -> IIAMService:
        """IAM acting as ``user`` (a Nexus user or its id): each call is decided
        by that user's policies. ``IamUnavailableError`` without an IAM service."""

    @abstractmethod
    def catalogs(self) -> CatalogRegistry:
        """The registered action catalogs, to validate documents against."""

    @abstractmethod
    def principal(self, principal_id: str) -> PrincipalRecord | None:
        """A principal's profile, to name it where the caller already sees its id."""

    @abstractmethod
    def policy(self, policy_id: str) -> Policy | None:
        """A policy, to name it where the caller already sees its id."""

    @abstractmethod
    def policies(self) -> list[Policy]:
        """Every policy, to offer those a caller may attach (the caller's own right
        to attach each is checked by IAM, not here)."""
