"""Publish existing LangChain tools to the tool registry.

Modules already expose capabilities three ways, and each maps onto a binding
without touching the tool implementations:

* a ready ``BaseTool`` instance (``tools/`` directory, module attributes):
  ``add_tool`` with a ``StaticToolBinding``;
* an ``Expose`` object (workflows, pipelines, tool classes): ``add_exposed``;
* an integration's ``as_tools(configuration)`` function, which needs
  credentials: ``add_factory`` with one ``FactoryToolBinding`` per produced
  tool. The factory runs once at publication to derive the definitions, then
  again at resolution with the caller's resolved configuration.

Definitions are derived from the tools themselves (name, description, the
model-facing argument schema), so an agent composed from the registry sees the
exact same contract as one built by hand.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from langchain_core.tools import BaseTool
from naas_abi_core.services.agent.tools.workspace_tools import REQUIRES_WORKSPACE_KEY
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ConfigRequirement,
    IToolRegistry,
    PublishedTool,
    ToolContext,
    ToolDefinition,
    ToolRegistryError,
    ToolRequirements,
)
from naas_abi_core.utils.Expose import Expose

ToolFactory = Callable[[Mapping[str, Any]], Sequence[BaseTool]]

# Stands in for missing configuration while deriving definitions. It is never
# used to resolve an executable tool.
DEFINITION_ONLY_PLACEHOLDER = "__abi_definition_only__"


def model_facing_name(name: str) -> str:
    """The name the agent runtime will expose to the model.

    Mirrors ``Agent.validate_name`` so a definition's name and the bound tool's
    name never diverge (the agent package is not imported here: this adapter
    stays usable without the agent runtime).
    """
    if re.match(r"^[a-zA-Z0-9_-]+$", name):
        return name
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name).replace("__", "_")


def _input_schema(tool: BaseTool) -> dict[str, Any]:
    # ``tool_call_schema`` is what the model sees: injected arguments
    # (state, tool call id, ...) are already stripped.
    schema = tool.tool_call_schema
    if isinstance(schema, dict):
        return dict(schema)
    try:
        return schema.model_json_schema()
    except Exception:  # noqa: BLE001 - fall back on the plain argument map
        return {"type": "object", "properties": dict(tool.args)}


def definition_from_tool(
    tool: BaseTool,
    *,
    namespace: str,
    module: str,
    version: str = "1",
    tags: Sequence[str] = (),
    required_scopes: Sequence[str] = (),
    requirements: Sequence[ConfigRequirement] = (),
    description: str | None = None,
) -> ToolDefinition:
    metadata = tool.metadata or {}
    return ToolDefinition(
        namespace=namespace,
        name=model_facing_name(tool.name),
        version=version,
        description=(description or tool.description or "").strip(),
        input_schema=_input_schema(tool),
        module=module,
        tags=tuple(tags),
        required_scopes=tuple(required_scopes),
        requirements=ToolRequirements(
            config=tuple(requirements),
            requires_workspace=bool(metadata.get(REQUIRES_WORKSPACE_KEY)),
        ),
    )


class StaticToolBinding:
    """Binding for a tool instance that needs no per-caller configuration."""

    def __init__(self, tool: BaseTool) -> None:
        self._tool = tool

    @property
    def default_config(self) -> Mapping[str, Any]:
        return {}

    def create(self, context: ToolContext, config: Mapping[str, Any]) -> BaseTool:
        return self._tool


class _SharedFactory:
    """One factory shared by every binding it produced, with a per-config cache.

    Building an integration once per configuration (not once per tool) keeps
    resolution cheap when an agent enables several tools of one integration.
    """

    def __init__(self, factory: ToolFactory) -> None:
        self._factory = factory
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, BaseTool]] = {}

    @staticmethod
    def _key(config: Mapping[str, Any]) -> str:
        encoded = json.dumps(dict(config), sort_keys=True, default=repr)
        return hashlib.sha256(encoded.encode()).hexdigest()

    def build(self, config: Mapping[str, Any]) -> dict[str, BaseTool]:
        key = self._key(config)
        with self._lock:
            cached = self._cache.get(key)
        if cached is not None:
            return cached
        built = {model_facing_name(t.name): t for t in self._factory(config)}
        with self._lock:
            return self._cache.setdefault(key, built)


class FactoryToolBinding:
    """Binding for one tool of an ``as_tools(configuration)`` style factory."""

    def __init__(
        self,
        factory: ToolFactory | _SharedFactory,
        tool_name: str,
        default_config: Mapping[str, Any] | None = None,
    ) -> None:
        self._factory = (
            factory if isinstance(factory, _SharedFactory) else _SharedFactory(factory)
        )
        self._tool_name = tool_name
        self._default_config = dict(default_config or {})

    @property
    def default_config(self) -> Mapping[str, Any]:
        return self._default_config

    def create(self, context: ToolContext, config: Mapping[str, Any]) -> BaseTool:
        tools = self._factory.build(config)
        tool = tools.get(self._tool_name)
        if tool is None:
            raise ToolRegistryError(
                f"The tool factory no longer produces '{self._tool_name}' "
                f"(it produced: {', '.join(sorted(tools)) or 'nothing'})."
            )
        return tool


class ToolPublisher:
    """Collects one module's tools, then publishes them in a single call."""

    def __init__(self, module: str, namespace: str | None = None) -> None:
        self.module = module
        self.namespace = namespace or module
        self._tools: dict[str, PublishedTool] = {}

    @property
    def tools(self) -> list[PublishedTool]:
        return list(self._tools.values())

    def _add(self, definition: ToolDefinition, binding: Any) -> ToolDefinition:
        tool_id = str(definition.id)
        if tool_id in self._tools:
            raise ToolRegistryError(
                f"Module '{self.module}' adds tool '{definition.name}' twice "
                f"({tool_id}). Give one of them another name or version."
            )
        self._tools[tool_id] = PublishedTool(definition=definition, binding=binding)
        return definition

    def add_tool(
        self,
        tool: BaseTool,
        *,
        version: str = "1",
        tags: Sequence[str] = (),
        required_scopes: Sequence[str] = (),
        description: str | None = None,
    ) -> ToolDefinition:
        definition = definition_from_tool(
            tool,
            namespace=self.namespace,
            module=self.module,
            version=version,
            tags=tags,
            required_scopes=required_scopes,
            description=description,
        )
        return self._add(definition, StaticToolBinding(tool))

    def add_tools(
        self, tools: Iterable[BaseTool], **options: Any
    ) -> list[ToolDefinition]:
        return [self.add_tool(tool, **options) for tool in tools]

    def add_exposed(self, exposed: Expose, **options: Any) -> list[ToolDefinition]:
        return self.add_tools(exposed.as_tools(), **options)

    def add_factory(
        self,
        factory: ToolFactory,
        *,
        default_config: Mapping[str, Any] | None = None,
        requirements: Sequence[ConfigRequirement] = (),
        version: str = "1",
        tags: Sequence[str] = (),
        required_scopes: Sequence[str] = (),
        include: Iterable[str] | None = None,
    ) -> list[ToolDefinition]:
        """Publish every tool ``factory`` produces (or only those in ``include``).

        The factory is called once with ``default_config`` to read the tool
        definitions. Required keys missing from it are filled with a
        placeholder for that call only, so a module can publish definitions
        before credentials exist; the factory must therefore not perform I/O
        while building tools.
        """
        defaults = dict(default_config or {})
        sample = dict(defaults)
        for requirement in requirements:
            if requirement.required and sample.get(requirement.key) in (None, ""):
                sample[requirement.key] = DEFINITION_ONLY_PLACEHOLDER

        shared = _SharedFactory(factory)
        produced = list(factory(sample))
        wanted = None if include is None else set(include)
        if wanted is not None:
            unknown = wanted - {model_facing_name(t.name) for t in produced}
            if unknown:
                raise ToolRegistryError(
                    f"include names tools the factory does not produce: "
                    f"{', '.join(sorted(unknown))}."
                )

        definitions: list[ToolDefinition] = []
        for tool in produced:
            name = model_facing_name(tool.name)
            if wanted is not None and name not in wanted:
                continue
            definition = definition_from_tool(
                tool,
                namespace=self.namespace,
                module=self.module,
                version=version,
                tags=tags,
                required_scopes=required_scopes,
                requirements=requirements,
            )
            definitions.append(
                self._add(definition, FactoryToolBinding(shared, name, defaults))
            )
        return definitions

    def publish_to(self, registry: IToolRegistry) -> None:
        registry.publish(self.module, self.tools)
