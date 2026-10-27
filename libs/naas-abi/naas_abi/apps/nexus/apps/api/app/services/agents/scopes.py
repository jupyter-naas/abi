"""Which module scope a workspace's agent is (core ``services/iam/module_scopes``).

An agent of a module, engine or remote, is ``agent/<module>/<name>`` of the
``module`` catalog: ``module:UseAgent`` in the workspace decides who uses it,
lists it and reaches it as a sub-agent. An agent a workspace builds itself
(a model and a prompt, no module class) has no module scope: ``nexus:UseAgent``
and the workspace's roles decide.

An engine module's workflows and pipelines reach an agent as tools: a turn binds
the ones the caller may run (``usable_process_scopes``), and the agent refuses
the others (``naas_abi_core.services.agent.context.tool_scope_refused``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentRecord
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import (
    REMOTE_PROVIDER,
    split_key,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.utils.public_urls import resolve_abi_module_path
from naas_abi_core import logger
from naas_abi_core.services.agent.context import process_scopes
from naas_abi_core.services.iam.module_scopes import AGENT


def agent_class_label(agent_cls: type | None) -> str | None:
    """An agent class's own name: its ``name`` attribute, else ``NAME``."""
    if agent_cls is None:
        return None
    name = getattr(agent_cls, "name", None)
    if isinstance(name, str):
        return name
    if isinstance(name, property):
        name = getattr(agent_cls, "NAME", None)
    return name if isinstance(name, str) else None


def class_scope(
    class_name: str, agent_cls: type | None, module_of: Mapping[str, str] | None = None
) -> ModuleScope | None:
    """The scope of an engine agent class (registry key ``<python module>/<Class>``):
    the engine module that loads it, and the class's own name."""
    python_module, _, class_part = class_name.partition("/")
    if not python_module or not class_part:
        return None
    module = (module_of or {}).get(class_name) or resolve_abi_module_path(python_module)
    name = agent_class_label(agent_cls) or class_part
    return ModuleScope(AGENT, module or python_module, name)


def agent_scope(
    agent: AgentRecord,
    classes: Mapping[str, type] | None = None,
    module_of: Mapping[str, str] | None = None,
) -> ModuleScope | None:
    """``agent``'s module scope, or None for an agent the workspace built."""
    if not agent.class_name:
        return None
    if agent.provider == REMOTE_PROVIDER:
        try:
            module_id, name = split_key(agent.class_name)
        except ValueError:
            return None
        return ModuleScope(AGENT, module_id, name)
    return class_scope(agent.class_name, (classes or {}).get(agent.class_name), module_of)


def engine_process_scopes() -> list[ModuleScope]:
    """The scope of every workflow and pipeline class of the engine's modules, as
    the engine registered them (``EngineProcessBridge.tag_process_scopes``): an
    agent's tool any instance of one exposes runs only within the caller's."""
    return [ModuleScope(*scope) for scope in process_scopes()]


async def usable_process_scopes(user: object, workspace_id: str) -> frozenset[tuple[str, str, str]]:
    """The engine workflows and pipelines the caller may run in ``workspace_id``
    (``agent_usable_module_scopes``)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import authz

    usable = await authz.filter_scopes(
        engine_process_scopes(), user=user, workspace=workspace_id, scope_of=lambda s: s
    )
    return frozenset((s.type, s.module, s.name) for s in usable)


def scope_resolver() -> Callable[[AgentRecord], ModuleScope | None]:
    """``agent_scope`` over the process's agent class registry."""
    from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary import (
        agents__primary_adapter__FastAPI as agents_api,
    )

    try:
        classes = agents_api._get_agent_class_registry()
        module_of = agents_api.agent_class_modules()
    except Exception:  # noqa: BLE001 - no engine loaded: the names alone decide
        logger.debug("Agent class registry unavailable for module scopes", exc_info=True)
        classes, module_of = {}, {}
    return lambda agent: agent_scope(agent, classes, module_of)
