"""The kernel services' action catalogs, registered with IAM at engine boot,
and the listers of the services loaded.

Each catalog lives next to its domain code (``services/<name>/iam_catalog.py``).
They are registered whether or not the service is loaded, so a
policy can name any kernel action and the built-in roles cover every kernel
resource type. A loaded service that can list its resources says so with
``iam_listers()`` (``AGENTS.md``, "Publishers and listing").
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.catalog import ActionCatalog
from naas_abi_core.services.iam.IAMPorts import IIAMService


def kernel_catalogs() -> tuple[ActionCatalog, ...]:
    from naas_abi_core.services.activity_log.iam_catalog import (
        CATALOG as ACTIVITY_LOG,
    )
    from naas_abi_core.services.cache.iam_catalog import CATALOG as CACHE
    from naas_abi_core.services.coding_environment.iam_catalog import (
        CATALOG as CODING_ENVIRONMENT,
    )
    from naas_abi_core.services.dataset.iam_catalog import CATALOG as DATASET
    from naas_abi_core.services.discovery.iam_catalog import CATALOG as DISCOVERY
    from naas_abi_core.services.document.iam_catalog import CATALOG as DOCUMENT
    from naas_abi_core.services.email.iam_catalog import CATALOG as EMAIL
    from naas_abi_core.services.event.iam_catalog import CATALOG as EVENT
    from naas_abi_core.services.iam.module_scopes import CATALOG as MODULE_SCOPES
    from naas_abi_core.services.identity.iam_catalog import CATALOG as IDENTITY
    from naas_abi_core.services.keyvalue.iam_catalog import CATALOG as KEYVALUE
    from naas_abi_core.services.model_registry.iam_catalog import (
        CATALOG as MODEL_REGISTRY,
    )
    from naas_abi_core.services.object_storage.iam_catalog import (
        CATALOG as OBJECT_STORAGE,
    )
    from naas_abi_core.services.secret.iam_catalog import CATALOG as SECRET
    from naas_abi_core.services.source_control.iam_catalog import (
        CATALOG as SOURCE_CONTROL,
    )
    from naas_abi_core.services.triple_store.iam_catalog import (
        CATALOG as TRIPLE_STORE,
    )
    from naas_abi_core.services.vector_store.iam_catalog import (
        CATALOG as VECTOR_STORE,
    )

    return (
        # Runtime services.
        ACTIVITY_LOG,
        CODING_ENVIRONMENT,
        DISCOVERY,
        EMAIL,
        EVENT,
        IDENTITY,
        MODEL_REGISTRY,
        SOURCE_CONTROL,
        # Data services.
        CACHE,
        DATASET,
        DOCUMENT,
        KEYVALUE,
        OBJECT_STORAGE,
        SECRET,
        TRIPLE_STORE,
        VECTOR_STORE,
        # What modules expose, grantable per workspace (not a service).
        MODULE_SCOPES,
    )


def register_kernel_catalogs(iam: IIAMService) -> None:
    """Register every kernel catalog, as the engine (it holds iam:RegisterCatalog)."""
    with as_service_account("engine"):
        for catalog in kernel_catalogs():
            iam.register_catalog(catalog)


def register_listers(iam: Any, owners: Iterable[Any]) -> list[tuple[str, str]]:
    """Register the listers each of ``owners`` offers (``iam_listers()``: a
    loaded kernel service, an engine module), in process: the types listed. One
    that IAM refuses (a type no registered catalog declares) is logged and left
    out: its type is offered as wildcards."""
    registered: list[tuple[str, str]] = []
    register = getattr(iam, "register_lister", None)
    if register is None:
        return registered  # IAM over NATS: the serving engine lists
    for owner in owners:
        offer = getattr(owner, "iam_listers", None)
        if owner is None or not callable(offer):
            continue
        try:
            listers = dict(offer() or {})
        except Exception as exc:  # noqa: BLE001 - one owner never stops the engine
            logger.error(f"{type(owner).__name__}: its listers are not used: {exc}")
            continue
        for (service, type_name), lister in listers.items():
            try:
                register(service, type_name, lister)
            except Exception as exc:  # noqa: BLE001 - offered as wildcards instead
                logger.error(f"Lister of {service}:{type_name} not registered: {exc}")
                continue
            registered.append((service, type_name))
    return registered


def register_kernel_listers(iam: Any, services: Iterable[Any]) -> list[tuple[str, str]]:
    """The listers of the kernel services loaded (``Engine.Services.all``)."""
    return register_listers(iam, services)
