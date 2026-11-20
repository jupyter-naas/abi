"""Deployment choices of the access model (ADR ``20261120_access_levels_and_groups``),
shared by mounted and standalone Nexus configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NexusModelsConfig(BaseModel):
    """Which models each level may chat with directly (``nexus_config.models``).

    ``member_set``: the canonical model ids (``model_registry`` ids, the ones
    ``/v1/models`` lists) of the policy "Models · member", the Member level's
    default set. Empty by default: a deployment names its own. Workspace and
    organization admins hold "Models · all"; Viewers hold no chat model. Every
    Member and Viewer may embed (search). An agent's own model is always
    allowed to whoever may use the agent, whatever their set.
    """

    model_config = ConfigDict(extra="forbid")

    member_set: list[str] = Field(default_factory=list)
