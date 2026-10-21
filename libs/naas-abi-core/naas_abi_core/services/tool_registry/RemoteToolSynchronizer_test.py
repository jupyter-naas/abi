"""Remote tools join the registry while their module is ready, and leave with it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from naas_abi_core.services.tool_registry.adapters.secondary.InMemoryToolIndexAdapter import (
    InMemoryToolIndexAdapter,
)
from naas_abi_core.services.tool_registry.RemoteToolSynchronizer import (
    RemoteToolSynchronizer,
)
from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
    CountingConceptEmbedder,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IRemoteToolDirectory,
    PublishedTool,
    RemoteModuleTools,
    RemoteToolDirectoryError,
    ToolContext,
    ToolDefinition,
    ToolNotFoundError,
)
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)
from naas_abi_core.services.tool_registry.ToolRegistryService_test import (
    RecordingBinding,
    _tool,
)

CRM = "acme.crm"
ISSUE = "acme.crm/open_ticket@1"


def remote_definition(
    name: str, description: str, module: str = CRM, **fields: Any
) -> ToolDefinition:
    return ToolDefinition(
        namespace=module,
        name=name,
        description=description,
        module=module,
        remote=True,
        **fields,
    )


class Directory(IRemoteToolDirectory):
    def __init__(self, *modules: RemoteModuleTools) -> None:
        self.modules = list(modules)
        self.failure: Exception | None = None
        self.reads = 0

    def list_modules(self) -> list[RemoteModuleTools]:
        self.reads += 1
        if self.failure is not None:
            raise self.failure
        return list(self.modules)


def crm(*definitions: ToolDefinition, major: int = 1) -> RemoteModuleTools:
    return RemoteModuleTools(CRM, major, tuple(definitions))


TICKET = remote_definition("open_ticket", "Open a new ticket for a customer issue.")
MAIL = remote_definition("send_email", "Send an email message to a recipient.")


@pytest.fixture
def registry() -> ToolRegistryService:
    service = ToolRegistryService()
    service.configure_search(CountingConceptEmbedder(), InMemoryToolIndexAdapter())
    return service


def synchronizer(registry, directory, bound=None, **kwargs) -> RemoteToolSynchronizer:
    def bind(definition: ToolDefinition, major: int) -> RecordingBinding:
        binding = RecordingBinding()
        if bound is not None:
            bound.append((str(definition.id), major, binding))
        return binding

    return RemoteToolSynchronizer(registry, directory, bind, **kwargs)


def ids(registry) -> list[str]:
    return [str(d.id) for d in registry.list_definitions()]


def test_the_tools_of_a_ready_module_are_published_under_its_id(registry):
    bound: list = []
    sync = synchronizer(registry, Directory(crm(TICKET, MAIL)), bound)
    assert sync.sync_once() is True
    assert ids(registry) == ["acme.crm/open_ticket@1", "acme.crm/send_email@1"]
    assert registry.get_definition(ISSUE).remote is True
    assert {(tool_id, major) for tool_id, major, _ in bound} == {
        ("acme.crm/open_ticket@1", 1),
        ("acme.crm/send_email@1", 1),
    }
    assert sync.published_modules == {CRM}


def test_a_remote_tool_is_found_by_a_paraphrase_and_drops_out_of_the_index(registry):
    directory = Directory(crm(TICKET, MAIL))
    sync = synchronizer(registry, directory)
    sync.sync_once()
    found = registry.search_tools("report a bug in our software", limit=3)
    assert found[0].tool_id == ISSUE
    directory.modules = []
    assert sync.sync_once() is True
    assert ids(registry) == []
    assert registry.search_tools("report a bug in our software", limit=3) == []
    with pytest.raises(ToolNotFoundError):
        registry.resolve(ISSUE, ToolContext())


def test_a_module_that_serves_no_ready_instance_is_unpublished_and_comes_back(registry):
    directory = Directory(crm(TICKET))
    sync = synchronizer(registry, directory)
    sync.sync_once()
    directory.modules = []
    sync.sync_once()
    assert ids(registry) == []
    directory.modules = [crm(TICKET)]
    assert sync.sync_once() is True
    assert ids(registry) == [ISSUE]


def test_a_read_that_changes_nothing_leaves_the_registry_and_the_index_alone(registry):
    directory = Directory(crm(TICKET))
    sync = synchronizer(registry, directory)
    sync.sync_once()
    registry.search_tools("report a bug", limit=1)
    embedder = registry._embedder
    embedded = len(embedder.embedded)
    assert sync.sync_once() is False
    assert sync.sync_once() is False
    registry.search_tools("report a bug", limit=1)
    assert len(embedder.embedded) == embedded


def test_a_change_of_the_tool_set_replaces_what_the_module_published(registry):
    directory = Directory(crm(TICKET, MAIL))
    sync = synchronizer(registry, directory)
    sync.sync_once()
    changed = remote_definition("open_ticket", "Raise a ticket, with a priority.")
    directory.modules = [crm(changed)]
    assert sync.sync_once() is True
    assert ids(registry) == [ISSUE]
    assert registry.get_definition(ISSUE).description.startswith("Raise")
    # A new contract generation rebinds, too.
    bound: list = []
    sync = synchronizer(registry, Directory(crm(changed, major=2)), bound)
    sync.sync_once()
    assert [major for _, major, _ in bound] == [2]


def test_an_unreadable_directory_keeps_what_is_published(registry):
    directory = Directory(crm(TICKET))
    sync = synchronizer(registry, directory)
    sync.sync_once()
    directory.failure = RemoteToolDirectoryError("discovery did not answer")
    assert sync.sync_once() is False
    assert ids(registry) == [ISSUE]
    directory.failure = None
    directory.modules = []
    assert sync.sync_once() is True
    assert ids(registry) == []


def test_a_remote_module_never_replaces_a_module_loaded_here(registry):
    registry.publish(CRM, [_tool(CRM, "local_tool", "A tool loaded in this process.")])
    sync = synchronizer(registry, Directory(crm(TICKET)), reserved={CRM})
    assert sync.sync_once() is False
    assert ids(registry) == ["acme.crm/local_tool@1"]
    assert sync.published_modules == frozenset()


def test_a_tool_another_module_already_publishes_is_refused_not_taken(registry):
    # A local module "other" publishes under the namespace a remote module serves.
    taken = PublishedTool(
        ToolDefinition(
            namespace=CRM,
            name="open_ticket",
            description="Open a ticket.",
            module="other",
        ),
        RecordingBinding(),
    )
    registry.publish("other", [taken])
    sync = synchronizer(registry, Directory(crm(TICKET)))
    assert sync.sync_once() is False
    assert registry.get_definition(ISSUE).remote is False
    assert sync.published_modules == frozenset()
    # The refusal is reported once: the same answer is not tried again.
    assert sync.sync_once() is False


def test_modules_without_tools_publish_nothing(registry):
    sync = synchronizer(registry, Directory(crm()))
    assert sync.sync_once() is False
    assert ids(registry) == []


def test_the_background_loop_follows_the_directory(registry):
    import threading

    directory = Directory(crm(TICKET))
    sync = synchronizer(registry, directory, refresh_seconds=0.05)
    sync.start()
    try:
        assert ids(registry) == [ISSUE]  # the first read is made by start()
        directory.modules = []
        deadline = threading.Event()
        for _ in range(100):
            if not ids(registry):
                break
            deadline.wait(0.05)
        assert ids(registry) == []
    finally:
        sync.stop()
    reads = directory.reads
    threading.Event().wait(0.2)
    assert directory.reads == reads  # stopped


def test_the_loop_outlives_a_failing_read(registry):
    class Flaky(Directory):
        def list_modules(self):
            self.reads += 1
            if self.reads == 1:
                raise RuntimeError("boom")
            return list(self.modules)

    sync = synchronizer(registry, Flaky(crm(TICKET)), refresh_seconds=0.05)
    sync.start()  # the first read raises: start() must not
    try:
        import time

        for _ in range(100):
            if ids(registry):
                break
            time.sleep(0.05)
        assert ids(registry) == [ISSUE]
    finally:
        sync.stop()


def test_a_refresh_must_be_positive(registry):
    with pytest.raises(ValueError):
        synchronizer(registry, Directory(), refresh_seconds=0)


def _unused(_: Mapping[str, Any]) -> None:  # keeps the import for typing
    pass
