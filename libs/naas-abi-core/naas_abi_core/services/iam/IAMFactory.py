"""Compose an ``IAMService``: a store, an authorizer, then the bootstrap.

The engine builds it from ``services.iam`` (``EngineConfiguration_IAMService``);
scripts and tests use the helpers below.
"""

from __future__ import annotations

from typing import Literal

from naas_abi_core.services.iam.IAMPorts import IAMSecrets, IAMStore
from naas_abi_core.services.iam.IAMService import AuthorizerFactory, IAMService

AuthorizerName = Literal["policy", "allow_all"]


def authorizer_factory(name: AuthorizerName) -> AuthorizerFactory | None:
    """``policy`` (None: the service's default) or the explicit ``allow_all`` opt-out."""
    if name == "policy":
        return None
    if name == "allow_all":
        from naas_abi_core.services.iam.adapters.secondary.authorizer__allow_all import (
            AllowAllAuthorizer,
        )

        return lambda _source: AllowAllAuthorizer()
    raise ValueError(f"Unknown IAM authorizer {name!r}")


def build(
    store: IAMStore,
    authorizer: AuthorizerName = "policy",
    *,
    cache_ttl_seconds: float = 60.0,
    bootstrap: bool = True,
    secrets: IAMSecrets | None = None,
    access_ttl_seconds: int = 600,
    key_rotation_days: int = 30,
    auto_approve: bool = False,
) -> IAMService:
    service = IAMService(
        store,
        authorizer_factory(authorizer),
        cache_ttl_seconds=cache_ttl_seconds,
        secrets=secrets,
        access_ttl_seconds=access_ttl_seconds,
        key_rotation_days=key_rotation_days,
        auto_approve=auto_approve,
    )
    if bootstrap:
        service.bootstrap()
    return service


def IAMServiceSQLite(
    path: str = "storage/iam/iam.sqlite", authorizer: AuthorizerName = "policy"
) -> IAMService:
    from naas_abi_core.services.iam.adapters.secondary.IAMStoreSQLite import (
        IAMStoreSQLite,
    )

    return build(IAMStoreSQLite(path), authorizer)


def IAMServicePostgreSQL(
    dsn: str, schema: str = "abi_iam", authorizer: AuthorizerName = "policy"
) -> IAMService:
    from naas_abi_core.services.iam.adapters.secondary.IAMStorePostgreSQL import (
        IAMStorePostgreSQL,
    )

    return build(IAMStorePostgreSQL(dsn, schema), authorizer)


def IAMServiceMemory(authorizer: AuthorizerName = "policy") -> IAMService:
    from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import (
        IAMStoreMemory,
    )

    return build(IAMStoreMemory(), authorizer)
