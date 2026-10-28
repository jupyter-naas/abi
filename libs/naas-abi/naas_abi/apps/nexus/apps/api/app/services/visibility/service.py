"""``WorkspaceVisibility``: the hidden module scopes of a workspace, by kind."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.services.visibility.port import VisibilityReaderPort

_log = logging.getLogger(__name__)


class WorkspaceVisibility:
    """Asks each kind's reader (``type`` -> reader) about its scopes. A kind with
    no reader hides nothing; a reader that fails hides every scope it was asked
    about (logged): a hidden resource is never used for a failed read."""

    def __init__(self, readers: Mapping[str, VisibilityReaderPort]) -> None:
        self._readers = dict(readers)

    async def hidden(self, workspace_id: str, scopes: Sequence[ModuleScope]) -> set[ModuleScope]:
        by_type: dict[str, list[ModuleScope]] = {}
        for scope in scopes:
            if scope.type in self._readers:
                by_type.setdefault(scope.type, []).append(scope)
        hidden: set[ModuleScope] = set()
        for type_name, asked in by_type.items():
            try:
                hidden |= await self._readers[type_name].hidden(workspace_id, asked)
            except Exception:  # noqa: BLE001 - fail closed: refused, never used
                _log.warning(
                    "The %s visibility of workspace %s could not be read: hidden",
                    type_name,
                    workspace_id,
                    exc_info=True,
                )
                hidden |= set(asked)
        return hidden

    async def is_hidden(self, workspace_id: str, scope: ModuleScope) -> bool:
        return scope in await self.hidden(workspace_id, [scope])
