"""``services.iam``: IAM's store, its authorizer, modules and tokens (RFC §11.1).

```yaml
services:
  iam:
    store:
      adapter: sqlite              # sqlite | postgres | memory
      path: storage/iam/iam.sqlite
      # dsn: "{{ secret.IAM_POSTGRES_DSN }}"
    authorizer: policy             # policy (default) | allow_all (explicit opt-out; warns at boot)
    modules:                       # reserved: read from subtask 6 (#60) on
      auto_approve: false          # true only in the abi dev overlay
    tokens:                        # reserved: read from subtasks 6 and 8 (#60, #62) on
      access_ttl_seconds: 600      # capped at 600
      key_rotation_days: 30
```

``modules`` and ``tokens`` are validated now, so a configuration written for the
next subtasks fails early when it is wrong, but nothing reads them yet.

``authorizer: allow_all`` is never a default: it must be written down, and the
engine warns at every boot that runs with it.
"""

from __future__ import annotations

from typing import Literal, Self

from naas_abi_core.services.iam.IAMPorts import IAMStore
from naas_abi_core.services.iam.IAMService import IAMService
from pydantic import BaseModel, ConfigDict, Field, model_validator


class IAMStoreConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    adapter: Literal["sqlite", "postgres", "memory"] = "sqlite"
    # sqlite
    path: str = "storage/iam/iam.sqlite"
    timeout: float = Field(default=5.0, gt=0)
    # postgres: an existing database; the tables go in their own schema.
    dsn: str | None = None
    schema_name: str = Field(default="abi_iam", alias="schema")
    connect_timeout: int = Field(default=5, ge=1)
    statement_timeout: int = Field(default=30000, ge=1)
    pool_size: int = Field(default=5, ge=1, le=50)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.adapter == "postgres" and not self.dsn:
            raise ValueError("services.iam.store: the postgres adapter needs a dsn")
        return self

    def load(self) -> IAMStore:
        if self.adapter == "sqlite":
            from naas_abi_core.services.iam.adapters.secondary.IAMStoreSQLite import (
                IAMStoreSQLite,
            )

            return IAMStoreSQLite(self.path, timeout=self.timeout)
        if self.adapter == "postgres":
            from naas_abi_core.services.iam.adapters.secondary.IAMStorePostgreSQL import (
                IAMStorePostgreSQL,
            )

            assert self.dsn is not None
            return IAMStorePostgreSQL(
                self.dsn,
                self.schema_name,
                connect_timeout=self.connect_timeout,
                statement_timeout_ms=self.statement_timeout,
                pool_size=self.pool_size,
            )
        from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import (
            IAMStoreMemory,
        )

        return IAMStoreMemory()

    def local_storage(self) -> str | None:
        """Where IAM's data lives (single-serving-engine ADR)."""
        if self.adapter == "sqlite":
            return f"SQLite at {self.path}"
        if self.adapter == "memory":
            return "this process, not persisted"
        return None  # postgres


class IAMModulesConfiguration(BaseModel):
    """Reserved: manifest approval reads it from subtask 6 (#60) on."""

    model_config = ConfigDict(extra="forbid")

    # Approve module permission manifests without review (subtask 6, #60):
    # only the abi dev overlay sets it.
    auto_approve: bool = False


class IAMTokensConfiguration(BaseModel):
    """Reserved: the token issuer reads it from subtasks 6 and 8 (#60, #62) on."""

    model_config = ConfigDict(extra="forbid")

    access_ttl_seconds: int = Field(default=600, ge=1, le=600)
    key_rotation_days: int = Field(default=30, ge=1)


class IAMServiceConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store: IAMStoreConfiguration = Field(default_factory=IAMStoreConfiguration)
    authorizer: Literal["policy", "allow_all"] = "policy"
    modules: IAMModulesConfiguration = Field(default_factory=IAMModulesConfiguration)
    tokens: IAMTokensConfiguration = Field(default_factory=IAMTokensConfiguration)
    # Effective policies are cached at most this long (RFC §5.6: 60 seconds).
    cache_ttl_seconds: float = Field(default=60.0, gt=0, le=60)

    def load(self) -> IAMService:
        """The service, bootstrapped, with every kernel catalog registered: the
        engine's root of trust is in place before any service serves."""
        from naas_abi_core.services.iam import IAMFactory
        from naas_abi_core.services.iam.kernel_catalogs import register_kernel_catalogs

        service = IAMFactory.build(
            self.store.load(),
            self.authorizer,
            cache_ttl_seconds=self.cache_ttl_seconds,
        )
        register_kernel_catalogs(service)
        return service

    def local_storage(self) -> str | None:
        return self.store.local_storage()
