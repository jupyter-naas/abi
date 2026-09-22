"""Expose already-loaded engine services over NATS, if configured to.

See docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md and
``EngineConfiguration.NATSConfiguration``'s docstring for the design this
implements: ``config.yaml``'s top-level ``nats:`` block is what turns this
on at all -- no per-service opt-in flag. When present, every loaded service
that has a NATS primary adapter available gets one started automatically,
wrapping the owning service instance. Local modules and other domains receive
NATS-backed facades, so their calls use the same endpoints as remote modules.
Service-level endpoints retain event publishing and prefix normalization.

Extending to another service means adding one more branch to
``expose_services`` below, following the same shape -- not a generic/
metaprogrammed dispatch, matching how ``EngineServiceLoader.load_services``
itself lists every service explicitly rather than looping over a registry.

``secret`` is exposed too, at Max's explicit direction, despite Stage 1's
shared-JWT auth having no per-caller ARN/IAM authorization yet -- anyone
holding a valid service token can read every secret this process's
``Secret`` service is configured with. Accepted as a known, temporary gap
("if it's adding security problems we will have to fix that anyway"), not
an oversight -- revisit once Stage 2 per-caller authorization exists. It
also has its own re-exposure guard shape (see ``expose_services`` below):
``Secret`` fans out over a *list* of adapters, not one, so it is skipped when
any configured adapter is itself a NATS client, preventing
recursive self-routing on the globally shared secret subjects.

Deliberately NOT exposed here, on purpose (see the RFC / dev log for the
full reasoning, not an oversight):
- ``model_registry`` -- has no secondary-adapter-port/``Literal[...,"custom"]``
  slot to hang a NATS client on at all, and its ``get*`` methods return live
  LangChain client objects bound to local credentials/HTTP sessions --
  fundamentally process-local, not serializable.
"""

from __future__ import annotations

from naas_abi_core import logger
from naas_abi_core.engine import nats_runtime
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.activity_log.adapters.primary.activity_log__primary_adapter__NATS import (
    ActivityLogPrimaryAdapterNATS,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSecondaryAdapterNATSClient import (
    ActivityLogSecondaryAdapterNATSClient,
)
from naas_abi_core.services.cache.adapters.primary.cache__primary_adapter__NATS import (
    CachePrimaryAdapterNATS,
)
from naas_abi_core.services.cache.adapters.secondary.CacheSecondaryAdapterNATSClient import (
    CacheSecondaryAdapterNATSClient,
)
from naas_abi_core.services.coding_environment.adapters.primary.coding_environment__primary_adapter__NATS import (
    CodingEnvironmentPrimaryAdapterNATS,
)
from naas_abi_core.services.coding_environment.adapters.secondary.CodingEnvironmentSecondaryAdapterNATSClient import (
    CodingEnvironmentSecondaryAdapterNATSClient,
)
from naas_abi_core.services.dataset.adapters.primary.dataset__primary_adapter__NATS import (
    DatasetPrimaryAdapterNATS,
)
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterNATSClient import (
    DatasetSecondaryAdapterNATSClient,
)
from naas_abi_core.services.email.adapters.primary.email__primary_adapter__NATS import (
    EmailPrimaryAdapterNATS,
)
from naas_abi_core.services.email.adapters.secondary.EmailSecondaryAdapterNATSClient import (
    EmailSecondaryAdapterNATSClient,
)
from naas_abi_core.services.event.adapters.primary.event__primary_adapter__NATS import (
    EventPrimaryAdapterNATS,
)
from naas_abi_core.services.event.adapters.secondary.EventSecondaryAdapterNATSClient import (
    EventSecondaryAdapterNATSClient,
)
from naas_abi_core.services.keyvalue.adapters.primary.keyvalue__primary_adapter__NATS import (
    KeyValuePrimaryAdapterNATS,
)
from naas_abi_core.services.keyvalue.adapters.secondary.KeyValueSecondaryAdapterNATSClient import (
    KeyValueSecondaryAdapterNATSClient,
)
from naas_abi_core.services.object_storage.adapters.primary.object_storage__primary_adapter__NATS import (
    ObjectStoragePrimaryAdapterNATS,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNATSClient import (
    ObjectStorageSecondaryAdapterNATSClient,
)
from naas_abi_core.services.secret.adaptors.primary.secret__primary_adapter__NATS import (
    SecretPrimaryAdapterNATS,
)
from naas_abi_core.services.secret.adaptors.secondary.SecretSecondaryAdapterNATSClient import (
    SecretSecondaryAdapterNATSClient,
)
from naas_abi_core.services.source_control.adapters.primary.source_control__primary_adapter__NATS import (
    SourceControlPrimaryAdapterNATS,
)
from naas_abi_core.services.source_control.adapters.secondary.SourceControlSecondaryAdapterNATSClient import (
    SourceControlSecondaryAdapterNATSClient,
)
from naas_abi_core.services.triple_store.adapters.primary.triple_store__primary_adapter__NATS import (
    TripleStorePrimaryAdapterNATS,
)
from naas_abi_core.services.triple_store.adapters.secondary.TripleStoreSecondaryAdapterNATSClient import (
    TripleStoreSecondaryAdapterNATSClient,
)
from naas_abi_core.services.vector_store.adapters.primary.vector_store__primary_adapter__NATS import (
    VectorStorePrimaryAdapterNATS,
)
from naas_abi_core.services.vector_store.adapters.secondary.VectorStoreSecondaryAdapterNATSClient import (
    VectorStoreSecondaryAdapterNATSClient,
)


class EngineNATSLoader:
    __configuration: EngineConfiguration

    def __init__(self, configuration: EngineConfiguration):
        self.__configuration = configuration

    def expose_services(self, services: IEngine.Services) -> list[object]:
        """Start a NATS primary adapter for every loaded service that has one.

        Returns the started primary-adapter instances -- there's no shutdown
        hook yet to hand them to (see the RFC's open questions), but a
        caller that wants to keep a reference for later can.
        """
        nats_config = self.__configuration.nats
        if nats_config is None:
            logger.debug("EngineNATSLoader: no nats: config, nothing to expose")
            return []

        nc = nats_runtime.get_connection(nats_config.nats_url)
        started: list[object] = []

        if services.object_storage_available() and not isinstance(
            services.object_storage.adapter, ObjectStorageSecondaryAdapterNATSClient
        ):
            # Wraps the domain SERVICE, not services.object_storage.adapter --
            # see ObjectStoragePrimaryAdapterNATS's docstring for why that
            # distinction matters (event publishing, prefix normalization).
            primary = ObjectStoragePrimaryAdapterNATS(
                services.object_storage, nats_config.jwt_secret
            )
            nats_runtime.run_coro(primary.start(nc))
            started.append(primary)
            logger.debug("EngineNATSLoader: exposed object_storage over NATS")
        elif services.object_storage_available():
            logger.debug(
                "EngineNATSLoader: object_storage is itself a NATS client "
                '(adapter: "nats_rpc") -- not re-exposing a remote proxy'
            )

        if services.secret_available() and not any(
            isinstance(adapter, SecretSecondaryAdapterNATSClient)
            for adapter in services.secret.adapters
        ):
            # A fanout containing a proxy must not serve its own global subject.
            # Dependency wiring rejects mixed local/remote ownership explicitly.
            primary_secret = SecretPrimaryAdapterNATS(
                services.secret, nats_config.jwt_secret
            )
            nats_runtime.run_coro(primary_secret.start(nc))
            started.append(primary_secret)
            logger.debug("EngineNATSLoader: exposed secret over NATS")
        elif services.secret_available():
            logger.debug(
                "EngineNATSLoader: secret contains NATS clients "
                "-- not re-exposing a remote proxy"
            )

        if services.dataset_available() and not isinstance(
            services.dataset.adapter, DatasetSecondaryAdapterNATSClient
        ):
            primary_dataset = DatasetPrimaryAdapterNATS(
                services.dataset, nats_config.jwt_secret
            )
            nats_runtime.run_coro(primary_dataset.start(nc))
            started.append(primary_dataset)
            logger.debug("EngineNATSLoader: exposed dataset over NATS")
        elif services.dataset_available():
            logger.debug(
                'EngineNATSLoader: dataset is itself a NATS client (adapter: "nats_rpc") '
                "-- not re-exposing a remote proxy"
            )

        if services.kv_available() and not isinstance(
            services.kv.adapter, KeyValueSecondaryAdapterNATSClient
        ):
            primary_kv = KeyValuePrimaryAdapterNATS(services.kv, nats_config.jwt_secret)
            nats_runtime.run_coro(primary_kv.start(nc))
            started.append(primary_kv)
            logger.debug("EngineNATSLoader: exposed kv over NATS")
        elif services.kv_available():
            logger.debug(
                'EngineNATSLoader: kv is itself a NATS client (adapter: "nats_rpc") '
                "-- not re-exposing a remote proxy"
            )

        if services.email_available() and not isinstance(
            services.email.adapter, EmailSecondaryAdapterNATSClient
        ):
            primary_email = EmailPrimaryAdapterNATS(
                services.email, nats_config.jwt_secret
            )
            nats_runtime.run_coro(primary_email.start(nc))
            started.append(primary_email)
            logger.debug("EngineNATSLoader: exposed email over NATS")
        elif services.email_available():
            logger.debug(
                'EngineNATSLoader: email is itself a NATS client (adapter: "nats_rpc") '
                "-- not re-exposing a remote proxy"
            )

        if services.activity_log_available() and not isinstance(
            services.activity_log.adapter, ActivityLogSecondaryAdapterNATSClient
        ):
            primary_activity_log = ActivityLogPrimaryAdapterNATS(
                services.activity_log, nats_config.jwt_secret
            )
            nats_runtime.run_coro(primary_activity_log.start(nc))
            started.append(primary_activity_log)
            logger.debug("EngineNATSLoader: exposed activity_log over NATS")
        elif services.activity_log_available():
            logger.debug(
                "EngineNATSLoader: activity_log is itself a NATS client "
                '(adapter: "nats_rpc") -- not re-exposing a remote proxy'
            )

        if services.coding_environment_available() and not isinstance(
            services.coding_environment.adapter,
            CodingEnvironmentSecondaryAdapterNATSClient,
        ):
            primary_coding_environment = CodingEnvironmentPrimaryAdapterNATS(
                services.coding_environment, nats_config.jwt_secret
            )
            nats_runtime.run_coro(primary_coding_environment.start(nc))
            started.append(primary_coding_environment)
            logger.debug("EngineNATSLoader: exposed coding_environment over NATS")
        elif services.coding_environment_available():
            logger.debug(
                "EngineNATSLoader: coding_environment is itself a NATS client "
                '(adapter: "nats_rpc") -- not re-exposing a remote proxy'
            )

        if services.events_available() and not isinstance(
            services.events.adapter, EventSecondaryAdapterNATSClient
        ):
            # Wraps the raw IEventAdapter, not the EventService domain object
            # -- EventService's extra behaviour (bus broadcasting) lives
            # above this port entirely, so there's no richer object to
            # prefer here the way object_storage prefers its domain service.
            primary_events = EventPrimaryAdapterNATS(
                services.events.adapter, nats_config.jwt_secret
            )
            nats_runtime.run_coro(primary_events.start(nc))
            started.append(primary_events)
            logger.debug("EngineNATSLoader: exposed event over NATS")
        elif services.events_available():
            logger.debug(
                'EngineNATSLoader: event is itself a NATS client (adapter: "nats_rpc") '
                "-- not re-exposing a remote proxy"
            )

        if services.source_control_available() and not isinstance(
            services.source_control.adapter, SourceControlSecondaryAdapterNATSClient
        ):
            primary_source_control = SourceControlPrimaryAdapterNATS(
                services.source_control, nats_config.jwt_secret
            )
            nats_runtime.run_coro(primary_source_control.start(nc))
            started.append(primary_source_control)
            logger.debug("EngineNATSLoader: exposed source_control over NATS")
        elif services.source_control_available():
            logger.debug(
                "EngineNATSLoader: source_control is itself a NATS client "
                '(adapter: "nats_rpc") -- not re-exposing a remote proxy'
            )

        if services.vector_store_available() and not isinstance(
            services.vector_store.adapter, VectorStoreSecondaryAdapterNATSClient
        ):
            # Wraps the raw IVectorStorePort -- VectorStoreService has no
            # richer event-publishing side effect at this port boundary to
            # preserve, unlike object_storage.
            primary_vector_store = VectorStorePrimaryAdapterNATS(
                services.vector_store.adapter, nats_config.jwt_secret
            )
            nats_runtime.run_coro(primary_vector_store.start(nc))
            started.append(primary_vector_store)
            logger.debug("EngineNATSLoader: exposed vector_store over NATS")
        elif services.vector_store_available():
            logger.debug(
                "EngineNATSLoader: vector_store is itself a NATS client "
                '(adapter: "nats_rpc") -- not re-exposing a remote proxy'
            )

        if services.triple_store_available() and not isinstance(
            services.triple_store.adapter, TripleStoreSecondaryAdapterNATSClient
        ):
            # Wraps the domain SERVICE, not services.triple_store.adapter --
            # TripleStoreService publishes TriplesInserted/TriplesRemoved/
            # GraphCreated/GraphCleared/GraphDropped events and does batched
            # bus notification on insert/remove, same rationale as
            # object_storage's primary adapter.
            primary_triple_store = TripleStorePrimaryAdapterNATS(
                services.triple_store, nats_config.jwt_secret
            )
            nats_runtime.run_coro(primary_triple_store.start(nc))
            started.append(primary_triple_store)
            logger.debug("EngineNATSLoader: exposed triple_store over NATS")
        elif services.triple_store_available():
            logger.debug(
                "EngineNATSLoader: triple_store is itself a NATS client "
                '(adapter: "nats_rpc") -- not re-exposing a remote proxy'
            )

        if services.cache_available() and not isinstance(
            services.cache.cold.adapter, CacheSecondaryAdapterNATSClient
        ):
            # v1 exposes one adapter. Use the canonical cold tier for remote callers.
            primary_cache = CachePrimaryAdapterNATS(
                services.cache.cold.adapter, nats_config.jwt_secret
            )
            nats_runtime.run_coro(primary_cache.start(nc))
            started.append(primary_cache)

        if services.cache_available():
            for index, (_, adapter) in enumerate(services.cache.adapters):
                if isinstance(adapter, CacheSecondaryAdapterNATSClient):
                    continue
                primary_tier = CachePrimaryAdapterNATS(
                    adapter,
                    nats_config.jwt_secret,
                    subject_prefix=f"abi.svc.cache.v1.tier.{index}",
                )
                nats_runtime.run_coro(primary_tier.start(nc))
                started.append(primary_tier)

        return started
