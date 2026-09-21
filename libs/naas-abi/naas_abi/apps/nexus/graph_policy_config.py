"""Workspace graph grants shared by mounted and standalone Nexus configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NEXUS_GRAPH = "http://ontology.naas.ai/graph/nexus"
SCHEMA_GRAPH = "http://ontology.naas.ai/graph/schema"


class WorkspaceGraphPolicyConfig(BaseModel):
    """Exact grants plus an explicit catalog-wide read option; omitted grants remain private."""

    model_config = ConfigDict(extra="forbid")

    read_all: bool = False
    read: list[str] = Field(default_factory=list)
    write: list[str] = Field(default_factory=list)
    include_owned: bool = True
    allow_create: bool = True

    @field_validator("read", "write")
    @classmethod
    def validate_graph_iris(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value.startswith(("https://", "http://", "urn:")) or any(
                ord(ch) <= 32 or ch in '<>"{}|^`\\*' for ch in value
            ):
                raise ValueError(
                    "Graph grants must be exact absolute IRIs; wildcards are not allowed"
                )
            if value == NEXUS_GRAPH:
                raise ValueError(
                    "The Nexus application catalog cannot be granted as a data graph"
                )
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def protect_schema(self) -> WorkspaceGraphPolicyConfig:
        if SCHEMA_GRAPH in self.write:
            raise ValueError("The schema graph can only be granted read access")
        return self
