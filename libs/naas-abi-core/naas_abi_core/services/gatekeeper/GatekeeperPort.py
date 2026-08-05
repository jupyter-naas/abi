from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

Sensitivity = Literal["normal", "sensitive"]


@dataclass(frozen=True)
class GatekeeperSubject:
    user_id: str | None
    workspace_id: str | None
    chat_id: str | None


@dataclass(frozen=True)
class GatekeeperResource:
    type: str
    id: str


@dataclass(frozen=True)
class GatekeeperDecision:
    allowed: bool
    reason: str
    observation_id: str | None = None


@dataclass(frozen=True)
class ResourceGrant:
    chat_id: str
    resource_type: str
    resource_id: str
    actions: frozenset[str]
    granted_at: datetime


@dataclass(frozen=True)
class ObservationRecord:
    id: str
    chat_id: str
    user_id: str | None
    workspace_id: str | None
    tool_name: str
    resource_type: str
    resource_id: str
    sensitivity: Sensitivity
    observed_at: datetime
    tool_args: dict[str, Any] = field(default_factory=dict)


class IObservationStore(ABC):
    @abstractmethod
    def record(self, observation: ObservationRecord) -> None:
        raise NotImplementedError()

    @abstractmethod
    def list_observations(self, chat_id: str) -> list[ObservationRecord]:
        raise NotImplementedError()

    @abstractmethod
    def shutdown(self) -> None:
        raise NotImplementedError()


class IGrantStore(ABC):
    @abstractmethod
    def grant(self, grant: ResourceGrant) -> None:
        raise NotImplementedError()

    @abstractmethod
    def list_grants(self, chat_id: str) -> list[ResourceGrant]:
        raise NotImplementedError()

    @abstractmethod
    def has_grant(
        self,
        chat_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def shutdown(self) -> None:
        raise NotImplementedError()


class IGatekeeperPolicy(ABC):
    @abstractmethod
    def classify_tool(self, tool_name: str) -> Sensitivity:
        raise NotImplementedError()

    @abstractmethod
    def extract_resources(
        self, tool_name: str, tool_args: dict[str, Any]
    ) -> list[GatekeeperResource]:
        raise NotImplementedError()

    @abstractmethod
    def required_action(self, tool_name: str) -> str:
        raise NotImplementedError()


class IGatekeeperDomain(ABC):
    @abstractmethod
    def evaluate_tool_call(
        self,
        subject: GatekeeperSubject,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
    ) -> GatekeeperDecision:
        raise NotImplementedError()

    @abstractmethod
    def record_tool_observation(
        self,
        subject: GatekeeperSubject,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
    ) -> ObservationRecord | None:
        raise NotImplementedError()

    @abstractmethod
    def grant_resource(
        self,
        chat_id: str,
        resource: GatekeeperResource,
        actions: frozenset[str],
    ) -> ResourceGrant:
        raise NotImplementedError()

    @abstractmethod
    def evaluate_conversation_export(
        self,
        subject: GatekeeperSubject,
        conversation_id: str,
    ) -> GatekeeperDecision:
        raise NotImplementedError()

    @abstractmethod
    def list_grants(self, chat_id: str) -> list[ResourceGrant]:
        raise NotImplementedError()

    @abstractmethod
    def list_observations(self, chat_id: str) -> list[ObservationRecord]:
        raise NotImplementedError()

    @abstractmethod
    def shutdown(self) -> None:
        raise NotImplementedError()


def new_observation_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_missing_grant_reason(reason: str) -> tuple[str, str, str] | None:
    """Parse ``missing_grant:{type}:{id}:{action}`` gatekeeper denial reasons."""
    prefix = "missing_grant:"
    if not reason.startswith(prefix):
        return None
    parts = reason[len(prefix) :].split(":", 2)
    if len(parts) != 3:
        return None
    resource_type, resource_id, action = parts
    if not resource_type or not resource_id or not action:
        return None
    return resource_type, resource_id, action
