"""The kernel services' action catalogs, registered with IAM at engine boot.

Each catalog lives next to its domain code (``services/<name>/iam_catalog.py``).
They are registered whether or not the service is loaded, so a
policy can name any kernel action and the built-in roles cover every kernel
resource type.
"""

from __future__ import annotations

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
    )


def register_kernel_catalogs(iam: IIAMService) -> None:
    """Register every kernel catalog, as the engine (it holds iam:RegisterCatalog)."""
    with as_service_account("engine"):
        for catalog in kernel_catalogs():
            iam.register_catalog(catalog)
