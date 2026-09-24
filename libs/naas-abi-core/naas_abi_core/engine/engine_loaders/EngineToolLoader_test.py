from types import SimpleNamespace

from langchain_core.tools import tool
from naas_abi_core.engine.engine_loaders.EngineToolLoader import EngineToolLoader
from naas_abi_core.module.Module import BaseModule
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)
from naas_abi_core.utils.Expose import Expose


@tool
def ping() -> str:
    """Ping."""
    return "pong"


@tool
def pong() -> str:
    """Pong."""
    return "ping"


class _Exposed(Expose):
    def as_tools(self):
        return [pong]


class _ExposedWithoutTools(Expose):
    def as_tools(self):
        raise NotImplementedError()


class _Module:
    def __init__(self, publish):
        self._publish = publish

    def publish_tools(self, publisher):
        self._publish(publisher)


def test_every_module_publishes_under_its_configured_name():
    registry = ToolRegistryService()
    counts = EngineToolLoader.publish_tools(
        registry,
        {
            "acme.one": _Module(lambda p: p.add_tool(ping)),
            "acme.two": _Module(lambda p: p.add_tools([ping, pong])),
        },
    )
    assert counts == {"acme.one": 1, "acme.two": 2}
    assert [str(d.id) for d in registry.list_definitions()] == [
        "acme.one/ping@1",
        "acme.two/ping@1",
        "acme.two/pong@1",
    ]


def test_a_failing_module_does_not_block_the_others():
    registry = ToolRegistryService()

    def broken(publisher):
        raise RuntimeError("cannot publish")

    counts = EngineToolLoader.publish_tools(
        registry,
        {
            "acme.broken": _Module(broken),
            "acme.ok": _Module(lambda p: p.add_tool(ping)),
        },
    )
    assert counts == {"acme.ok": 1}
    assert [str(d.id) for d in registry.list_definitions()] == ["acme.ok/ping@1"]


def test_the_default_hook_publishes_discovered_tool_instances():
    from naas_abi_core.services.tool_registry.adapters.primary.LangChainToolPublisher import (
        ToolPublisher,
    )

    module = SimpleNamespace(tools=[ping, _Exposed(), _ExposedWithoutTools(), object()])
    publisher = ToolPublisher("acme.module")
    BaseModule.publish_tools(module, publisher)  # type: ignore[arg-type]
    assert sorted(p.definition.name for p in publisher.tools) == ["ping", "pong"]
