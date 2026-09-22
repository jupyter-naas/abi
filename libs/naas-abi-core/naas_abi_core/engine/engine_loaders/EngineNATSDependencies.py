"""Composition root for network-only dependencies between engine domains.

Owners keep local persistence adapters. Only their injected dependency container
contains remote clients. Proxies are never passed to the endpoint exposer.
"""

from typing import Any

from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSecondaryAdapterNATSClient import (
    ActivityLogSecondaryAdapterNATSClient,
)
from naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter import (
    NATSJetStreamAdapter,
)
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.cache.adapters.secondary.CacheSecondaryAdapterNATSClient import (
    CacheSecondaryAdapterNATSClient,
)
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.coding_environment.adapters.secondary.CodingEnvironmentSecondaryAdapterNATSClient import (
    CodingEnvironmentSecondaryAdapterNATSClient,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterNATSClient import (
    DatasetSecondaryAdapterNATSClient,
)
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_core.services.email.adapters.secondary.EmailSecondaryAdapterNATSClient import (
    EmailSecondaryAdapterNATSClient,
)
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.event.adapters.secondary.EventSecondaryAdapterNATSClient import (
    EventSecondaryAdapterNATSClient,
)
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.services.keyvalue.adapters.secondary.KeyValueSecondaryAdapterNATSClient import (
    KeyValueSecondaryAdapterNATSClient,
)
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNATSClient import (
    ObjectStorageSecondaryAdapterNATSClient,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.adaptors.secondary.SecretSecondaryAdapterNATSClient import (
    SecretSecondaryAdapterNATSClient,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter
from naas_abi_core.services.source_control.adapters.secondary.SourceControlSecondaryAdapterNATSClient import (
    SourceControlSecondaryAdapterNATSClient,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)
from naas_abi_core.services.triple_store.adapters.secondary.TripleStoreSecondaryAdapterNATSClient import (
    TripleStoreSecondaryAdapterNATSClient,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.adapters.secondary.VectorStoreSecondaryAdapterNATSClient import (
    VectorStoreSecondaryAdapterNATSClient,
)
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from rdflib import Graph, URIRef


class RemoteTripleStoreService(TripleStoreService):
    """The owning service publishes mutation events and triple notifications once."""

    def _bootstrap_schema_graph(self) -> None:
        # Only the owning domain bootstraps schema state.
        pass

    def insert(self, triples: Graph, graph_name: URIRef) -> None:
        return self.adapter.insert(triples, graph_name)

    def remove(self, triples: Graph, graph_name: URIRef) -> None:
        return self.adapter.remove(triples, graph_name)


class EngineNATSDependencies:
    def __init__(self, config: NATSConfiguration):
        self.config = config
        self.clients: list[Any] = []

    def _client(self, cls, **kwargs):
        client = cls(self.config.nats_url, self.config.jwt_secret, "engine", **kwargs)
        self.clients.append(client)
        return client

    def _adapter(self, owner, cls):
        if isinstance(owner.adapter, cls):
            self.clients.append(owner.adapter)
            return owner.adapter
        return self._client(cls)

    def build(self, owners: IEngine.Services) -> IEngine.Services:
        values: dict[str, Any] = {}
        if owners.bus_available():
            if isinstance(owners.bus.adapter, NATSJetStreamAdapter):
                self.clients.append(owners.bus.adapter)
            bus_adapter = NATSJetStreamAdapter(self.config.nats_url)
            self.clients.append(bus_adapter)
            values["bus"] = BusService(bus_adapter)
        if owners.object_storage_available():
            values["object_storage"] = ObjectStorageService(
                self._adapter(
                    owners.object_storage, ObjectStorageSecondaryAdapterNATSClient
                )
            )
        if owners.dataset_available():
            values["dataset"] = DatasetService(
                self._adapter(owners.dataset, DatasetSecondaryAdapterNATSClient)
            )
        if owners.kv_available():
            values["kv"] = KeyValueService(
                self._adapter(owners.kv, KeyValueSecondaryAdapterNATSClient)
            )
        if owners.email_available():
            values["email"] = EmailService(
                self._adapter(owners.email, EmailSecondaryAdapterNATSClient)
            )
        if owners.activity_log_available():
            values["activity_log"] = ActivityLogService(
                self._adapter(
                    owners.activity_log, ActivityLogSecondaryAdapterNATSClient
                )
            )
        if owners.coding_environment_available():
            values["coding_environment"] = CodingEnvironmentService(
                self._adapter(
                    owners.coding_environment,
                    CodingEnvironmentSecondaryAdapterNATSClient,
                )
            )
        if owners.source_control_available():
            values["source_control"] = SourceControlService(
                self._adapter(
                    owners.source_control, SourceControlSecondaryAdapterNATSClient
                )
            )
        if owners.vector_store_available():
            values["vector_store"] = VectorStoreService(
                self._adapter(
                    owners.vector_store, VectorStoreSecondaryAdapterNATSClient
                )
            )
        if owners.events_available():
            values["events"] = EventService(
                self._adapter(owners.events, EventSecondaryAdapterNATSClient),
                bus=values.get("bus"),
            )
        if owners.secret_available():
            remote: list[ISecretAdapter] = [
                a
                for a in owners.secret.adapters
                if isinstance(a, SecretSecondaryAdapterNATSClient)
            ]
            if remote and len(remote) != len(owners.secret.adapters):
                raise ValueError(
                    "NATS mode cannot expose a mixed local/remote secret fanout; configure one owner"
                )
            if remote:
                self.clients.extend(remote)
            values["secret"] = Secret(
                remote or [self._client(SecretSecondaryAdapterNATSClient)]
            )
        if owners.triple_store_available():
            values["triple_store"] = RemoteTripleStoreService(
                self._adapter(
                    owners.triple_store, TripleStoreSecondaryAdapterNATSClient
                )
            )
        if owners.cache_available():
            self.clients.extend(
                adapter
                for _, adapter in owners.cache.adapters
                if isinstance(adapter, CacheSecondaryAdapterNATSClient)
            )
            values["cache"] = CacheService(
                adapters=[
                    (
                        tier,
                        adapter
                        if isinstance(adapter, CacheSecondaryAdapterNATSClient)
                        else self._client(
                            CacheSecondaryAdapterNATSClient,
                            subject_prefix=f"abi.svc.cache.v1.tier.{index}",
                        ),
                    )
                    for index, (tier, adapter) in enumerate(owners.cache.adapters)
                ]
            )
        # No fallback to process-local model objects across a domain boundary.
        dependencies = IEngine.Services(**values)
        if dependencies.triple_store_available():
            dependencies.triple_store.set_services(
                IEngine.Services(bus=values.get("bus"))
            )
        # These two primaries expose raw adapters, so the client facade owns events.
        for key in ("cache", "vector_store"):
            if key in values:
                values[key].set_services(IEngine.Services(events=values.get("events")))
        self.services = dependencies
        # Model registration remains a module-local capability, never injected
        # into domain services as a cross-domain dependency.
        self.module_services = IEngine.Services(
            **values,
            model_registry=(
                owners.model_registry if owners.model_registry_available() else None
            ),
        )
        return dependencies

    def close(self) -> None:
        clients, self.clients = self.clients, []
        for client in reversed(clients):
            try:
                client.close()
            except Exception as exc:  # noqa: BLE001 - close every owned transport
                logger.warning(
                    f"Error closing domain transport {type(client).__name__}: {exc}"
                )
