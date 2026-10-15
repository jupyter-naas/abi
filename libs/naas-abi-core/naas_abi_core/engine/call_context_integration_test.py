"""Every kernel domain service sees the same caller, in process and over NATS.

Each service is replaced by a recording stand-in: a subclass of the real
service whose every attribute access records ``current_call_context()`` and
stops the call. The real NATS primary adapter serves it on a local
nats-server. The same ``CallContext`` must reach it through ``ServicesProxy``
(in process), through the core RPC client and through the SDK transport.
Requires a local nats-server executable.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any

import nats
import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    current_call_context,
    service_account,
    use_call_context,
    user,
)
from naas_abi_core.engine.EngineProxy import ServicesProxy
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.engine.nats_test_server import (
    native_nats_server,
    nats_server_binary,
)
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from naas_abi_core.services.activity_log.adapters.primary.activity_log__primary_adapter__NATS import (
    ActivityLogPrimaryAdapterNATS,
)
from naas_abi_core.services.cache.adapters.primary.cache__primary_adapter__NATS import (
    CachePrimaryAdapterNATS,
)
from naas_abi_core.services.cache.CacheService import (
    CacheService,
    SingleTierCacheService,
)
from naas_abi_core.services.coding_environment.adapters.primary.coding_environment__primary_adapter__NATS import (
    CodingEnvironmentPrimaryAdapterNATS,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)
from naas_abi_core.services.dataset.adapters.primary.dataset__primary_adapter__NATS import (
    DatasetPrimaryAdapterNATS,
)
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_core.services.discovery.adapters.primary.discovery_nats import (
    DiscoveryNATS,
)
from naas_abi_core.services.discovery.discovery_service import DiscoveryService
from naas_abi_core.services.document.adapters.primary.document__primary_adapter__NATS import (
    DocumentPrimaryAdapterNATS,
)
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_core.services.email.adapters.primary.email__primary_adapter__NATS import (
    EmailPrimaryAdapterNATS,
)
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.event.adapters.primary.event__primary_adapter__NATS import (
    EventPrimaryAdapterNATS,
)
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.services.keyvalue.adapters.primary.keyvalue__primary_adapter__NATS import (
    KeyValuePrimaryAdapterNATS,
)
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.model_registry.adapters.primary.model_registry_nats import (
    ModelRegistryNATS,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.object_storage.adapters.primary.object_storage__primary_adapter__NATS import (
    ObjectStoragePrimaryAdapterNATS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.adaptors.primary.secret__primary_adapter__NATS import (
    SecretPrimaryAdapterNATS,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.source_control.adapters.primary.source_control__primary_adapter__NATS import (
    SourceControlPrimaryAdapterNATS,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)
from naas_abi_core.services.triple_store.adapters.primary.triple_store__primary_adapter__NATS import (
    TripleStorePrimaryAdapterNATS,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.adapters.primary.vector_store__primary_adapter__NATS import (
    VectorStorePrimaryAdapterNATS,
)
from naas_abi_core.services.vector_store.adapters.secondary.VectorStoreSecondaryAdapterNATSClient import (
    VectorStoreSecondaryAdapterNATSClient,
)
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from naas_abi_proto.activity_log.v1 import activity_log_pb2
from naas_abi_proto.cache.v1 import cache_pb2
from naas_abi_proto.coding_environment.v1 import coding_environment_pb2
from naas_abi_proto.dataset.v1 import dataset_pb2
from naas_abi_proto.discovery.v1 import discovery_pb2
from naas_abi_proto.document.v1 import document_pb2
from naas_abi_proto.email.v1 import email_pb2
from naas_abi_proto.event.v1 import event_pb2
from naas_abi_proto.keyvalue.v1 import keyvalue_pb2
from naas_abi_proto.model_registry.v1 import model_registry_pb2
from naas_abi_proto.object_storage.v1 import object_storage_pb2
from naas_abi_proto.secret.v1 import secret_pb2
from naas_abi_proto.source_control.v1 import source_control_pb2
from naas_abi_proto.triple_store.v1 import triple_store_pb2
from naas_abi_proto.vector_store.v1 import vector_store_pb2
from naas_abi_sdk.transport import RPCError, Transport

pytestmark = pytest.mark.skipif(
    nats_server_binary() is None, reason="nats-server is not installed"
)

SECRET = "call-context-integration-secret-32b"
# Nexus serving a signed-in user: the RFC's "api on behalf of the user".
CALLER = CallContext(
    principal=service_account("api"),
    on_behalf_of=user("usr-ada"),
    workspace_id="ws-1",
    trace_id="trace-1",
)


class Reached(Exception):
    """The call reached the domain service; nothing more to do."""


def recording(cls: type, seen: list[CallContext]) -> Any:
    """An instance of ``cls`` that records the caller of any use of it."""

    class Recording(cls):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            pass

        def __getattribute__(self, name: str) -> Any:
            if name.startswith("__"):
                return object.__getattribute__(self, name)
            seen.append(current_call_context())
            raise Reached(name)

    return Recording()


@dataclass(frozen=True)
class Kernel:
    name: str
    service: type  # what the NATS primary serves
    primary: Callable[[Any], Any]
    subject: str
    request: Any
    response: type
    proxied: str | None  # the ServicesProxy attribute; None: not proxied
    proxied_service: type | None = None  # if ServicesProxy hands out another type


KERNELS = [
    Kernel(
        "activity_log",
        ActivityLogService,
        lambda s: ActivityLogPrimaryAdapterNATS(s, SECRET),
        "abi.svc.activity_log.v1.list_actors",
        activity_log_pb2.ListActorsRequest(),
        activity_log_pb2.ListActorsResponse,
        "activity_log",
    ),
    Kernel(
        "cache",
        SingleTierCacheService,
        lambda s: CachePrimaryAdapterNATS(s, SECRET),
        "abi.svc.cache.v1.exists",
        cache_pb2.ExistsRequest(key="k"),
        cache_pb2.ExistsResponse,
        "cache",
        CacheService,
    ),
    Kernel(
        "coding_environment",
        CodingEnvironmentService,
        lambda s: CodingEnvironmentPrimaryAdapterNATS(s, SECRET),
        "abi.svc.coding_environment.v1.list_templates",
        coding_environment_pb2.ListTemplatesRequest(),
        coding_environment_pb2.ListTemplatesResponse,
        "coding_environment",
    ),
    Kernel(
        "dataset",
        DatasetService,
        lambda s: DatasetPrimaryAdapterNATS(s, SECRET),
        "abi.svc.dataset.v1.list",
        dataset_pb2.ListRequest(namespace="ns"),
        dataset_pb2.ListResponse,
        "dataset",
    ),
    Kernel(
        "discovery",
        DiscoveryService,
        lambda s: DiscoveryNATS(s, SECRET, "test"),
        "abi.discovery.test.v1.list_modules",
        discovery_pb2.ListModulesRequest(),
        discovery_pb2.ListModulesResponse,
        None,
    ),
    Kernel(
        "document",
        DocumentService,
        lambda s: DocumentPrimaryAdapterNATS(s, SECRET),
        "abi.svc.document.v1.collections",
        document_pb2.CollectionsRequest(namespace="module"),
        document_pb2.CollectionsResponse,
        "document",
    ),
    Kernel(
        "email",
        EmailService,
        lambda s: EmailPrimaryAdapterNATS(s, SECRET),
        "abi.svc.email.v1.send",
        email_pb2.SendRequest(
            to_email="ada@example.com", subject="hello", text_body="hi"
        ),
        email_pb2.SendResponse,
        "email",
    ),
    Kernel(
        "event",
        EventService,
        lambda s: EventPrimaryAdapterNATS(s, SECRET),
        "abi.svc.event.v1.max_seq",
        event_pb2.MaxSeqRequest(),
        event_pb2.MaxSeqResponse,
        "events",
    ),
    Kernel(
        "keyvalue",
        KeyValueService,
        lambda s: KeyValuePrimaryAdapterNATS(s, SECRET),
        "abi.svc.keyvalue.v1.exists",
        keyvalue_pb2.ExistsRequest(key="k"),
        keyvalue_pb2.ExistsResponse,
        "kv",
    ),
    Kernel(
        "model_registry",
        ModelRegistryService,
        lambda s: ModelRegistryNATS(s, SECRET),
        "abi.svc.model_registry.v1.list_models",
        model_registry_pb2.ListModelsRequest(),
        model_registry_pb2.ListModelsResponse,
        "model_registry",
    ),
    Kernel(
        "object_storage",
        ObjectStorageService,
        lambda s: ObjectStoragePrimaryAdapterNATS(s, SECRET),
        "abi.svc.object_storage.v1.list_objects",
        object_storage_pb2.ListObjectsRequest(prefix="p"),
        object_storage_pb2.ListObjectsResponse,
        "object_storage",
    ),
    Kernel(
        "secret",
        Secret,
        lambda s: SecretPrimaryAdapterNATS(s, SECRET),
        "abi.svc.secret.v1.list",
        secret_pb2.ListRequest(),
        secret_pb2.ListResponse,
        "secret",
    ),
    Kernel(
        "source_control",
        SourceControlService,
        lambda s: SourceControlPrimaryAdapterNATS(s, SECRET),
        "abi.svc.source_control.v1.list_repos",
        source_control_pb2.ListReposRequest(),
        source_control_pb2.ListReposResponse,
        "source_control",
    ),
    Kernel(
        "triple_store",
        TripleStoreService,
        lambda s: TripleStorePrimaryAdapterNATS(s, SECRET),
        "abi.svc.triple_store.v1.query",
        triple_store_pb2.QueryRequest(query="SELECT * WHERE { ?s ?p ?o }"),
        triple_store_pb2.QueryResponse,
        "triple_store",
    ),
    Kernel(
        "vector_store",
        VectorStoreService,
        lambda s: VectorStorePrimaryAdapterNATS(s, SECRET),
        "abi.svc.vector_store.v1.list_collections",
        vector_store_pb2.ListCollectionsRequest(),
        vector_store_pb2.ListCollectionsResponse,
        "vector_store",
    ),
]


@pytest.fixture(scope="module")
def broker(tmp_path_factory):
    with native_nats_server(tmp_path_factory.mktemp("nats")) as url:
        yield url


def _in_process(kernel: Kernel) -> list[CallContext]:
    """What the service sees when called in process, through ServicesProxy."""
    seen: list[CallContext] = []
    service = recording(kernel.proxied_service or kernel.service, seen)
    with use_call_context(CALLER):
        try:
            if kernel.proxied is None:
                service.list_modules  # noqa: B018 - the access is the call
            else:
                engine = SimpleNamespace(
                    services=SimpleNamespace(**{kernel.proxied: service})
                )
                proxy = ServicesProxy(
                    engine,  # type: ignore[arg-type]
                    "platform",
                    ModuleDependencies([], []),
                    unlocked=True,
                )
                getattr(proxy, kernel.proxied).anything()
        except Reached:
            pass
    return seen


def _over_nats(url: str, kernel: Kernel, send) -> list[CallContext]:
    """What the service sees when ``send(url, kernel)`` calls it over NATS."""
    seen: list[CallContext] = []
    primary = kernel.primary(recording(kernel.service, seen))

    async def scenario() -> None:
        nc = await nats.connect(url)
        try:
            await primary.start(nc)
            await nc.flush()
            with use_call_context(CALLER):
                await send(url, kernel)
        finally:
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())
    return seen


async def _core_client(url: str, kernel: Kernel) -> None:
    client = NatsRPCClient(url, SECRET, "api")

    def call() -> None:
        request = type(kernel.request)()
        request.CopyFrom(kernel.request)
        request.context.CopyFrom(client._context())
        client._call(kernel.subject, request, kernel.response)

    try:
        await asyncio.to_thread(call)  # copies the caller's context, as callers do
    finally:
        await asyncio.to_thread(client.close)


async def _sdk_transport(url: str, kernel: Kernel) -> None:
    transport = Transport(url, issue_service_token("api", SECRET), forward_user=True)
    try:
        await transport.call(kernel.subject, kernel.request, kernel.response)
    except RPCError:
        pass  # the recording service stopped the call
    finally:
        await transport.close()


@pytest.mark.parametrize("kernel", KERNELS, ids=lambda kernel: kernel.name)
@pytest.mark.parametrize(
    "send", [_core_client, _sdk_transport], ids=["core_client", "sdk_transport"]
)
def test_the_service_sees_the_same_caller_in_process_and_over_nats(
    broker, kernel, send
):
    assert _in_process(kernel) == [CALLER]
    assert _over_nats(broker, kernel, send) == [CALLER]


def test_a_streamed_call_runs_as_the_caller_who_opened_it(broker):
    seen: list[CallContext] = []
    primary = VectorStorePrimaryAdapterNATS(recording(VectorStoreService, seen), SECRET)

    async def scenario() -> None:
        nc = await nats.connect(url := broker)
        client = VectorStoreSecondaryAdapterNATSClient(url, SECRET, "api")

        def read() -> None:
            with client.list_vectors_stream("docs") as documents:
                list(documents)

        try:
            await primary.start(nc)
            await nc.flush()
            with use_call_context(CALLER), pytest.raises(Exception):
                await asyncio.to_thread(read)
        finally:
            await asyncio.to_thread(client.close)
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())
    assert seen == [CALLER]


def test_a_synchronous_engine_client_sends_its_callers_user(broker):
    """``ModelRegistryNATSClient`` runs SDK coroutines on the engine's shared
    loop (``nats_runtime.run_coro``); the call still carries the caller of the
    thread that made it."""
    from naas_abi_core.services.model_registry.adapters.secondary.model_registry_client import (
        ModelRegistryNATSClient,
    )

    seen: list[CallContext] = []
    primary = ModelRegistryNATS(recording(ModelRegistryService, seen), SECRET)

    def call() -> None:
        client = ModelRegistryNATSClient(ModelRegistryService(), broker, SECRET)
        try:
            with use_call_context(CALLER), pytest.raises(RPCError):
                client.list_canonical_ids()
        finally:
            client.close()

    async def scenario() -> None:
        nc = await nats.connect(broker)
        try:
            await primary.start(nc)
            await nc.flush()
            await asyncio.to_thread(call)  # a plain thread, as a sync caller
        finally:
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())
    assert seen == [replace(CALLER, principal=service_account("engine"))]


@pytest.mark.parametrize("inside_a_users_call", [False, True])
def test_a_module_calls_as_itself_and_for_nobody(broker, inside_a_users_call):
    """A module's transport never names a user, even inside a user's call,
    so it is never refused for it."""
    keyvalue = next(kernel for kernel in KERNELS if kernel.name == "keyvalue")
    seen: list[CallContext] = []
    primary = keyvalue.primary(recording(KeyValueService, seen))
    around = (
        CALLER if inside_a_users_call else CallContext(principal=service_account("x"))
    )

    async def scenario() -> None:
        nc = await nats.connect(broker)
        transport = Transport(broker, issue_service_token("module/acme/people", SECRET))
        try:
            await primary.start(nc)
            await nc.flush()
            with use_call_context(around), pytest.raises(RPCError):
                await transport.call(
                    keyvalue.subject, keyvalue.request, keyvalue.response
                )
        finally:
            await transport.close()
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())
    [context] = seen
    assert context.principal == service_account("module/acme/people")
    assert context.on_behalf_of is None and context.user is None


def test_only_trusted_identities_may_name_a_user(broker):
    keyvalue = next(kernel for kernel in KERNELS if kernel.name == "keyvalue")
    seen: list[CallContext] = []
    primary = keyvalue.primary(recording(KeyValueService, seen))

    async def scenario() -> RPCError:
        nc = await nats.connect(broker)
        # A module forwarding a user: refused until delegated tokens exist.
        transport = Transport(
            broker,
            issue_service_token("module/acme/people", SECRET),
            forward_user=True,
        )
        try:
            await primary.start(nc)
            await nc.flush()
            with use_call_context(CALLER), pytest.raises(RPCError) as refused:
                await transport.call(
                    keyvalue.subject, keyvalue.request, keyvalue.response
                )
            return refused.value
        finally:
            await transport.close()
            await primary.stop()
            await nc.close()

    refused = asyncio.run(scenario())
    assert refused.code == "UNAUTHENTICATED"
    assert "on-behalf-of refused" in str(refused)
    assert seen == []
