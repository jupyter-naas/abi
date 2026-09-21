"""Workspace assignments: YAML seeds once, administrators own subsequent edits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from naas_abi.apps.nexus.graph_policy_config import WorkspaceGraphPolicyConfig
from pydantic import BaseModel, ConfigDict, Field

ResourceKind = Literal["ontologies", "graphs"]


class OntologyAssignments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: list[str] = Field(default_factory=list, max_length=10000)


@dataclass(frozen=True)
class ResourcePolicy:
    data: dict
    revision: int
    updated_by: str | None = None


class PolicyConflictError(Exception):
    """Another administrator saved this policy after the editor loaded it."""


class ResourcePolicyPort(Protocol):
    async def get_or_seed(
        self, workspace_id: str, kind: ResourceKind, seed: dict
    ) -> ResourcePolicy: ...
    async def save(
        self,
        workspace_id: str,
        kind: ResourceKind,
        data: dict,
        revision: int,
        user_id: str,
    ) -> ResourcePolicy: ...


def validate_policy(kind: ResourceKind, data: dict) -> dict:
    if kind == "graphs":
        return WorkspaceGraphPolicyConfig.model_validate(data).model_dump()
    return OntologyAssignments.model_validate(data).model_dump()


class ResourceAccessService:
    def __init__(self, repository: ResourcePolicyPort):
        self.repository = repository

    async def load(
        self, workspace_id: str, kind: ResourceKind, seed: dict
    ) -> ResourcePolicy:
        return await self.repository.get_or_seed(
            workspace_id, kind, validate_policy(kind, seed)
        )

    async def save(
        self,
        workspace_id: str,
        kind: ResourceKind,
        data: dict,
        revision: int,
        user_id: str,
        role: str,
    ) -> ResourcePolicy:
        if role not in {"owner", "admin"}:
            raise PermissionError("Workspace admin role required")
        return await self.repository.save(
            workspace_id, kind, validate_policy(kind, data), revision, user_id
        )
