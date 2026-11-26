"""Capability groups: one thing added to a level (ADR
``20261120_access_levels_and_groups``, decision 5).

Made on demand, never by default: none exists until someone asks for one
(``ensure_capability``). Each is a group holding one policy:

| Group | Policy | Attached |
|---|---|---|
| "Workflow runners" | "Workflow runners", the organization's, a sub-policy of "<O> access": ``RunWorkflow``, ``ReadWorkflowRuns``, ``RunPipeline``, ``ReadPipelineRuns`` on ``${scope}/module:workflow/*`` and ``.../pipeline/*`` | at ``${my workspaces}``: each workspace of the organization its member is in, through its "<W> workspace" membership group |
| "Models · all" | the platform's "Models · all" (``model_sets``) | without a scope |

"Models · all" is the platform's group, one per deployment, not an
organization's: IAM attaches a group an organization owns only at a scope there
or below, and a scope reaches only what is in it, never the platform's models.

A Member in "Workflow runners" runs workflows and pipelines in the workspaces
they belong to (core ``${my workspaces}``, within the organization that owns the
group and the policy); one outside it runs none. Which workflows is bounded by the
organization's offer (the policy's parent); a workspace's own allow-list bounds it
only where IAM bounds a ``${my workspaces}`` grant by it (a Deny in it wins).

Written as ``api`` for no user: the caller (S2/S6's routes) authorized the
request first. Idempotent: found by owner and name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import SECTIONS
from naas_abi_core.services.iam import module_scopes
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError
from naas_abi_core.services.iam.names import MY_CONTAINERS_SCOPE, PLATFORM
from naas_abi_core.services.iam.policy import POLICY_VERSION

Capability = Literal["workflow_runners", "models_all"]
WORKFLOW_RUNNERS = "Workflow runners"
MODELS_ALL = "Models · all"
NAMES: dict[str, str] = {"workflow_runners": WORKFLOW_RUNNERS, "models_all": MODELS_ALL}
RUNNERS_DESCRIPTION = (
    "Lets its Members run the workflows and pipelines their workspaces offer. Made on "
    "demand, owned by the organization."
)


def workflow_runners_document() -> dict[str, Any]:
    statements = []
    for kind in ("workflows", "pipelines"):
        sid, actions = SECTIONS[kind]
        type_name = module_scopes.WORKFLOW if kind == "workflows" else module_scopes.PIPELINE
        statements.append(
            {
                "sid": sid.replace("Offer", "Run"),
                "effect": "Allow",
                "actions": [f"{module_scopes.SERVICE}:{a}" for a in actions],
                "resources": [f"${{scope}}/{module_scopes.SERVICE}:{type_name}/*"],
            }
        )
    return {"version": POLICY_VERSION, "statements": statements}


@dataclass(frozen=True)
class CapabilityGroup:
    capability: str
    group_id: str
    policy_id: str
    scope: str | None


def _pages(listing: Any, **kwargs: Any) -> list[Any]:
    found: list[Any] = []
    after: str | None = None
    while True:
        page = listing(limit=500, after=after, **kwargs)
        found += list(page.items)
        after = page.next_after
        if not after:
            return found


def _group(iam: Any, name: str, container: str) -> str:
    for group in _pages(iam.list_groups, scope=container):
        if group.owner_scope == container and group.name == name and group.status != "deleted":
            return str(group.id)
    from naas_abi.apps.nexus.apps.api.app.services.iam.group_descriptions import described

    return str(
        iam.create_group(name, scope=container, description=described(name, owner=container)).id
    )


def _runners_policy(iam: Any, container: str, parent: str | None) -> str:
    for policy in _pages(iam.list_policies, scope=container):
        if (policy.owner_scope, policy.name) == (container, WORKFLOW_RUNNERS):
            return str(policy.id)
    return str(
        iam.create_policy(
            WORKFLOW_RUNNERS,
            workflow_runners_document(),
            description=RUNNERS_DESCRIPTION,
            scope=container,
            parent=parent,
        ).id
    )


def _attach(iam: Any, policy_id: str, group_id: str, scope: str | None) -> None:
    held = iam.list_attachments(principal_id=group_id)
    if not any((a.policy_id, a.scope) == (policy_id, scope) for a in held):
        iam.attach_policy(policy_id, group_id, scope)


def ensure_capability(
    iam: Any,
    org_id: str,
    capability: Capability,
    *,
    org_access: str | None = None,
    attach_at: str | None = None,
) -> CapabilityGroup:
    """The capability group (made if missing) holding its policy: "Workflow
    runners" of ``org_id``, or the platform's "Models · all" (``org_id`` unused).
    ``org_access``: "<O> access", the parent of "Workflow runners" (its bound);
    ``attach_at``: where "Workflow runners" is attached (``${my workspaces}`` by
    default). As ``api``."""
    name = NAMES[capability]
    if capability == "workflow_runners":
        container = org_container(org_id)
        group_id = _group(iam, name, container)
        policy_id = _runners_policy(iam, container, org_access)
        scope: str | None = attach_at or MY_CONTAINERS_SCOPE
    elif capability == "models_all":
        from naas_abi.apps.nexus.apps.api.app.services.iam.model_sets import model_policies

        group_id = _group(iam, name, PLATFORM)
        policy_id = model_policies(iam).all
        scope = None
    else:
        raise ValueError(f"{capability!r} is not a capability")
    _attach(iam, policy_id, group_id, scope)
    return CapabilityGroup(capability, group_id, policy_id, scope)


def find_capability(iam: Any, org_id: str, capability: Capability) -> str | None:
    """The capability group's id, or None when it was never made. As ``api``."""
    container = PLATFORM if capability == "models_all" else org_container(org_id)
    try:
        groups = _pages(iam.list_groups, scope=container)
    except IAMNotFoundError:
        return None
    name = NAMES[capability]
    for group in groups:
        if group.owner_scope == container and group.name == name and group.status != "deleted":
            return str(group.id)
    return None


__all__ = [
    "CapabilityGroup",
    "MODELS_ALL",
    "WORKFLOW_RUNNERS",
    "ensure_capability",
    "find_capability",
    "workflow_runners_document",
]
