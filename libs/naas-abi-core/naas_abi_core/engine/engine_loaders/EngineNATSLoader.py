"""Expose already-loaded engine services over NATS, if configured to.

See docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md and
``EngineConfiguration.NATSConfiguration``'s docstring for the design this
implements: ``config.yaml``'s top-level ``nats:`` block is what turns this
on at all -- no per-service opt-in flag. When present, every loaded service
that has a NATS primary adapter available gets one started automatically,
wrapping the *same* service instance every in-process caller already uses
(so remote callers get identical behaviour -- event publishing, prefix
normalization, whatever the domain service does beyond the raw adapter).

Deliberately narrow today: only ``object_storage`` has a primary adapter
built. Extending to another service means adding one more branch to
``expose_services`` below, following the same shape -- not a generic/
metaprogrammed dispatch, matching how ``EngineServiceLoader.load_services``
itself lists every service explicitly rather than looping over a registry.
"""

from __future__ import annotations

from naas_abi_core import logger
from naas_abi_core.engine import nats_runtime
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.object_storage.adapters.primary.object_storage__primary_adapter__NATS import (
    ObjectStoragePrimaryAdapterNATS,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNATSClient import (
    ObjectStorageSecondaryAdapterNATSClient,
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
                "(adapter: \"nats_rpc\") -- not re-exposing a remote proxy"
            )

        return started
