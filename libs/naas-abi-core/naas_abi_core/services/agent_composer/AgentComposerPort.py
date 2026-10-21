"""Record schema, ports and exceptions for composing agents from data.

An agent record (``AgentSpec``) describes an agent without code: its prompt,
its model, the registry tools it binds, the sub-agents it supervises and
whether it may discover more tools at runtime. The composer consumes a
validated record; where records are stored is the concern of an
``IAgentSpecRepository`` adapter.

Records reference credentials, they never contain them: a configuration value
is a literal (string, number, boolean, null) or ``{"secret": "<KEY>"}``,
resolved through ``ISecretResolverPort`` at composition time.

A hand-written record::

    kind: abi.agent/v1
    name: triage
    description: Files and routes bug reports.
    prompt: |
      You triage bug reports. File an issue for every confirmed bug.
    model: gpt-4.1-mini                       # or {id: ..., provider: ...}; omit for the default
    tools:
      - naas_abi_marketplace.applications.github/githubintegration_create_issue@1
      - tool: acme.tracker/create_ticket
        config:
          api_token: {secret: TRACKER_TOKEN}
    sub_agents:
      - researcher                            # another record's name
    capabilities:
      enabled: true                           # adds search/enable/disable tools
      allow: ["naas_abi_marketplace.applications.github/*"]
      max_enabled: 5
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from naas_abi_core.services.tool_registry.ToolRegistryPort import ToolRef

AGENT_SPEC_KIND: Literal["abi.agent/v1"] = "abi.agent/v1"
AGENT_NAME_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


# --------------------------------------------------------------------------- #
# Exceptions                                                                   #
# --------------------------------------------------------------------------- #


class AgentCompositionError(Exception):
    """A record (or specification) cannot be turned into a working agent.

    ``problems`` lists every issue found, so one failed attempt reports all of
    them instead of the first.
    """

    def __init__(self, agent: str, problems: Sequence[str]):
        self.agent = agent
        self.problems = tuple(problems)
        details = "\n".join(f"  - {problem}" for problem in self.problems)
        super().__init__(f"Agent '{agent}' cannot be composed:\n{details}")


class AgentSpecNotFoundError(AgentCompositionError, LookupError):
    def __init__(self, name: str):
        super().__init__(name, [f"no agent record named '{name}' exists"])


class AgentSpecInvalidError(AgentCompositionError):
    """A stored record does not match the schema."""


class SubAgentCycleError(AgentCompositionError):
    def __init__(self, cycle: Sequence[str]):
        self.cycle = tuple(cycle)
        super().__init__(
            self.cycle[0],
            [
                "sub-agent references form a cycle: " + " -> ".join(self.cycle),
            ],
        )


class ToolNameCollisionError(AgentCompositionError):
    """Two capabilities would reach the model under the same tool name."""


# --------------------------------------------------------------------------- #
# Record schema                                                                #
# --------------------------------------------------------------------------- #


class SecretRef(BaseModel):
    """A reference to a secret, resolved when the agent is composed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    secret: str = Field(min_length=1)


ConfigValue = SecretRef | str | int | float | bool | None


class ModelRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    provider: str | None = None


class ToolBindingSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: str
    config: dict[str, ConfigValue] = Field(default_factory=dict)

    @field_validator("tool")
    @classmethod
    def _valid_ref(cls, value: str) -> str:
        ToolRef.parse(value)
        return value

    @property
    def ref(self) -> ToolRef:
        return ToolRef.parse(self.tool)


class SubAgentRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    agent: str = Field(pattern=AGENT_NAME_PATTERN)


class CapabilitiesSpec(BaseModel):
    """Runtime tool discovery (see ``CapabilityAgent``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    # fnmatch patterns over tool ids the agent may enable.
    allow: list[str] = Field(default_factory=lambda: ["*"], min_length=1)
    max_enabled: int = Field(default=10, ge=1)
    # Configuration for tools enabled at runtime, keyed by full tool id.
    tool_config: dict[str, dict[str, ConfigValue]] = Field(default_factory=dict)


class AgentSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["abi.agent/v1"] = AGENT_SPEC_KIND
    name: str = Field(pattern=AGENT_NAME_PATTERN)
    description: str = ""
    prompt: str = Field(min_length=1)
    model: ModelRef | None = None
    tools: list[ToolBindingSpec] = Field(default_factory=list)
    sub_agents: list[SubAgentRef] = Field(default_factory=list)
    capabilities: CapabilitiesSpec = CapabilitiesSpec()

    @field_validator("model", mode="before")
    @classmethod
    def _model_short_form(cls, value: Any) -> Any:
        return {"id": value} if isinstance(value, str) else value

    @field_validator("tools", mode="before")
    @classmethod
    def _tools_short_form(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [{"tool": v} if isinstance(v, str) else v for v in value]
        return value

    @field_validator("sub_agents", mode="before")
    @classmethod
    def _sub_agents_short_form(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [{"agent": v} if isinstance(v, str) else v for v in value]
        return value

    @model_validator(mode="after")
    def _no_duplicates(self) -> AgentSpec:
        tools = [str(binding.ref) for binding in self.tools]
        duplicated_tools = sorted({t for t in tools if tools.count(t) > 1})
        if duplicated_tools:
            raise ValueError(
                f"tools lists {', '.join(duplicated_tools)} more than once"
            )
        agents = [ref.agent for ref in self.sub_agents]
        duplicated_agents = sorted({a for a in agents if agents.count(a) > 1})
        if duplicated_agents:
            raise ValueError(
                f"sub_agents lists {', '.join(duplicated_agents)} more than once"
            )
        return self


# --------------------------------------------------------------------------- #
# Secondary ports                                                              #
# --------------------------------------------------------------------------- #


class IAgentSpecRepository(ABC):
    """Where agent records live. The composer never assumes a backend."""

    @abstractmethod
    def get(self, name: str) -> AgentSpec:
        """Raise ``AgentSpecNotFoundError`` when absent."""

    @abstractmethod
    def list(self) -> list[AgentSpec]:
        """Every record, sorted by name."""

    @abstractmethod
    def save(self, spec: AgentSpec) -> None:
        """Create or replace the record named ``spec.name``."""

    @abstractmethod
    def delete(self, name: str) -> None:
        """Raise ``AgentSpecNotFoundError`` when absent."""


class ISecretResolverPort(ABC):
    @abstractmethod
    def resolve(self, key: str) -> str | None:
        """The secret's value, or ``None`` when it is not set."""
