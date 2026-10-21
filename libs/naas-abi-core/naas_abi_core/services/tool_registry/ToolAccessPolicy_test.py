import pytest

from naas_abi_core.services.tool_registry.ToolAccessPolicy import ScopeToolAccessPolicy
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ToolAccessDeniedError,
    ToolAction,
    ToolContext,
    ToolDefinition,
)


def _definition(*scopes: str) -> ToolDefinition:
    return ToolDefinition(
        namespace="acme",
        name="tool",
        description="A tool.",
        module="acme",
        required_scopes=scopes,
    )


@pytest.mark.parametrize("action", list(ToolAction))
def test_public_tools_are_allowed_for_everyone(action):
    ScopeToolAccessPolicy().check(_definition(), ToolContext(), action)


@pytest.mark.parametrize("action", list(ToolAction))
def test_every_required_scope_must_be_held(action):
    policy = ScopeToolAccessPolicy()
    with pytest.raises(ToolAccessDeniedError, match="finance"):
        policy.check(
            _definition("github", "finance"), ToolContext(scopes={"github"}), action
        )
    policy.check(
        _definition("github", "finance"),
        ToolContext(scopes={"github", "finance", "extra"}),
        action,
    )


def test_the_error_names_the_action_and_the_tool():
    with pytest.raises(
        ToolAccessDeniedError, match=r"Cannot enable tool 'acme/tool@1'"
    ):
        ScopeToolAccessPolicy().check(
            _definition("admin"), ToolContext(), ToolAction.ENABLE
        )
