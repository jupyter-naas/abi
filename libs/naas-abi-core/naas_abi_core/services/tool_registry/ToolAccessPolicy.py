"""Default access policy: a caller needs every scope a tool requires."""

from __future__ import annotations

from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IToolAccessPolicy,
    ToolAccessDeniedError,
    ToolAction,
    ToolContext,
    ToolDefinition,
)


class ScopeToolAccessPolicy(IToolAccessPolicy):
    """Grants discover, enable and execute alike when the scopes match.

    A tool without ``required_scopes`` is public. Hosts that need finer rules
    (per action, per workspace, role mappings) provide their own
    ``IToolAccessPolicy``.
    """

    def check(
        self, definition: ToolDefinition, context: ToolContext, action: ToolAction
    ) -> None:
        missing = sorted(set(definition.required_scopes) - context.scopes)
        if missing:
            raise ToolAccessDeniedError(
                f"Cannot {action.value} tool '{definition.id}': the caller lacks "
                f"scope(s) {', '.join(missing)}."
            )
