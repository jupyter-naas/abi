"""What a workspace shows: each agent, app, workflow and pipeline of its set is
on or off there, for everyone in it.

A kind keeps its own state (``agent_configs.enabled``, ``app_configs.enabled``,
``workflow_visibility``); a reader of each kind tells which of some module
scopes the workspace turned off.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope


class VisibilityReaderPort(ABC):
    """One kind's on and off in a workspace."""

    @abstractmethod
    async def hidden(self, workspace_id: str, scopes: Sequence[ModuleScope]) -> set[ModuleScope]:
        """The ``scopes`` the workspace turned off."""
