"""What Workspace settings > General › Features needs: IAM as the caller (the IAM
admin pages' ``IamGateway``) and where it records which policy it wrote for each
feature of a workspace.

Who may use a feature is a policy's, always: each feature of a workspace gets one
policy "Feature · <name>" owned by the workspace, a sub-policy of "<W> access", and
the choice (Everyone, Only…, Nobody) is where it is attached. The record says which
policy that is; it is never found by its name.
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
