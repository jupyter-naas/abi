"""Resolve the model id an agent class uses, statically where possible.

Agent classes wire their chat model in a handful of ways:

* a class attribute ``model = "<id>"`` (e.g. ``CodingAgent``);
* a module-level ``MODEL = "<id>"`` constant (domain-expert templates);
* an import ``from <...>.models.<x> import model`` inside ``create_agent``
  (marketplace AI agents such as ``ClaudeAgent``, ``GrokAgent``);
* an engine-config reference ``<...>.configuration.<name>_model``
  (``AbiAgent``, ``OntologyEngineerAgent``).

Instantiating an agent to read ``agent.chat_model`` is too expensive to do for
every agent on a list request — each ``IntentAgent`` loads a spaCy model and the
supervisor eagerly builds all sub-agents. So we extract the *declared* model id
without executing the agent module beyond the class object the registry already
holds: a cheap class-attribute read, falling back to an ``ast`` parse of the
agent source file.

The extracted id is canonicalized against the marketplace model catalog so it
matches the models settings page, which keys on canonical id / model id.
"""

from __future__ import annotations

import ast
import inspect
from functools import cache

from naas_abi.apps.nexus.apps.api.app.services.providers.model_catalog import (
    find_catalog_model,
    find_catalog_model_by_module_path,
)
from naas_abi_core import logger


def resolve_agent_model_id(agent_cls: type) -> str | None:
    """Return the canonical model id an agent class is wired to, or ``None``.

    Resolution order (first hit wins): class attribute ``model`` → module-level
    ``MODEL``/``MODEL_ID`` → ``from <...>.models.<x> import model`` import →
    ``configuration.<name>_model`` engine-config reference. The raw id is then
    canonicalized against the catalog; when it matches a known model the stable
    canonical id is returned so it links to the models page.
    """
    raw = _raw_model_id(agent_cls)
    if not raw:
        return None
    entry = find_catalog_model(raw)
    return entry.canonical_id if entry is not None else raw


def _raw_model_id(agent_cls: type) -> str | None:
    candidate = _class_attr_model(agent_cls)
    if candidate:
        return candidate
    return _ast_model_id(agent_cls)


def _class_attr_model(agent_cls: type) -> str | None:
    """Read a plain ``model = "<id>"`` class attribute (ignoring properties)."""
    value = getattr(agent_cls, "model", None)
    return value if isinstance(value, str) and value else None


@cache
def _ast_model_id(agent_cls: type) -> str | None:
    """Extract the declared model id from the agent's source file via ``ast``."""
    try:
        source = inspect.getsource(inspect.getmodule(agent_cls))  # type: ignore[arg-type]
        tree = ast.parse(source)
    except (OSError, TypeError, SyntaxError):
        return None

    return (
        _module_level_model(tree)
        or _imported_model(tree)
        or _config_model(tree)
    )


def _module_level_model(tree: ast.Module) -> str | None:
    """A module-level ``MODEL`` / ``MODEL_ID`` string constant."""
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
        if not any(isinstance(t, ast.Name) and t.id in ("MODEL", "MODEL_ID") for t in targets):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value:
            return value.value
    return None


def _imported_model(tree: ast.Module) -> str | None:
    """Resolve a ``from <...>.models.<x> import model`` import to its model id."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if ".models." not in f"{node.module}." and not node.module.endswith(".models"):
            continue
        if not any(alias.name == "model" for alias in node.names):
            continue
        entry = find_catalog_model_by_module_path(node.module)
        if entry is not None:
            # The import pins one exact model file, so use its canonical id
            # directly — re-matching by the provider model_id could collide with
            # another file that ships the same provider model_id.
            return entry.canonical_id
    return None


def _config_model(tree: ast.Module) -> str | None:
    """Resolve a ``<...>.configuration.<name>_model`` reference via engine config."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if not (node.attr.endswith("_model") and not node.attr.endswith("_provider")):
            continue
        if not (isinstance(node.value, ast.Attribute) and node.value.attr == "configuration"):
            continue
        value = _config_value(node.attr)
        if value:
            return value
    return None


def _config_value(attr_name: str) -> str | None:
    try:
        from naas_abi import ABIModule

        value = getattr(ABIModule.get_instance().configuration, attr_name, None)
    except Exception:
        logger.debug("Could not read engine config attribute %r", attr_name)
        return None
    return value if isinstance(value, str) and value else None
