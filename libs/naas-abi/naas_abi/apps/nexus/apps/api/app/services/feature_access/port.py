"""What Workspace settings > General › Features needs: IAM as the caller (the IAM
admin pages' ``IamGateway``) and the record of the "Feature · <name>" policies an
older version wrote.

What a workspace offers is its access policy's, "<W> access" (``iam/workspace_offer``):
Everyone is the feature offered there, Nobody not offered. An older version wrote
one policy "Feature · <name>" per feature, attached where the choice was; the record
(``FeaturePolicyStore``) still says which, so Access › Policies marks them until the
access migration (S4) retires them. Nothing writes it any more.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection
from dataclasses import dataclass
from typing import Literal

Choice = Literal["everyone", "only", "nobody"]
CHOICES: tuple[Choice, ...] = ("everyone", "only", "nobody")


@dataclass(frozen=True)
class FeatureChange:
    """Who may use ``feature`` in the workspace: its members (``everyone``), the
    users and groups named (``only``), or nobody."""

    feature: str
    choice: Choice
    principals: tuple[str, ...] = ()


class FeaturePolicyStore(ABC):
    @abstractmethod
    async def policies(self, workspace_id: str) -> dict[str, str]:
        """``{feature: policy id}`` of the policies written for the workspace."""

    @abstractmethod
    async def put(self, workspace_id: str, feature: str, policy_id: str) -> None:
        """Record (or replace) the policy written for ``feature``."""

    @abstractmethod
    async def managed_among(self, policy_ids: Collection[str]) -> dict[str, str]:
        """``{policy id: feature}`` for those of ``policy_ids`` written here."""
