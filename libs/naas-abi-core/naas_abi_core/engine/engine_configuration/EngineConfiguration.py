import os
import sys
from collections.abc import Iterable, Mapping
from io import StringIO
from typing import Any, Literal, Self

import yaml
from jinja2 import ChainableUndefined, Environment, FileSystemLoader
from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ActivityLogService import (
    ActivityLogAdapterConfiguration,
    ActivityLogServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_BusService import (
    BusAdapterConfiguration,
    BusAdapterPythonQueueConfiguration,
    BusServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_CacheService import (
    TIER_COLD,
    TIER_HOT,
    CacheAdapterEntry,
    CacheAdapterObjectStorageConfiguration,
    CacheAdapterRedisConfiguration,
    CacheServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_CodingEnvironmentService import (
    CodingEnvironmentAdapterConfiguration,
    CodingEnvironmentServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_DatasetService import (
    DatasetAdapterConfiguration,
    DatasetAdapterDuckLakeConfiguration,
    DatasetServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_Deploy import (
    DeployConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_Dev import (
    DevConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_DocumentService import (
    DocumentServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_EmailService import (
    EmailAdapterConfiguration,
    EmailAdapterSMTPConfiguration,
    EmailServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_EventService import (
    EventAdapterConfiguration,
    EventAdapterSqliteConfiguration,
    EventServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_KeyValueService import (
    KeyValueAdapterConfiguration,
    KeyValueAdapterPythonConfiguration,
    KeyValueServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ModelRegistryService import (
    ModelRegistryServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageAdapterConfiguration,
    ObjectStorageAdapterFSConfiguration,
    ObjectStorageServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_SecretService import (
    DotenvSecretConfiguration,
    SecretAdapterConfiguration,
    SecretServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_SourceControlService import (
    SourceControlAdapterConfiguration,
    SourceControlServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_TripleStoreService import (
    TripleStoreAdapterConfiguration,
    TripleStoreAdapterOxigraphEmbeddedConfiguration,
    TripleStoreServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_VectorStoreService import (
    VectorStoreAdapterConfiguration,
    VectorStoreAdapterQdrantInMemoryConfiguration,
    VectorStoreServiceConfiguration,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter
from pydantic import BaseModel, ConfigDict, Field, model_validator
from rich.prompt import Prompt


class ServicesConfiguration(BaseModel):
    document: DocumentServiceConfiguration = Field(
        default_factory=DocumentServiceConfiguration
    )
    object_storage: ObjectStorageServiceConfiguration = (
        ObjectStorageServiceConfiguration(
            object_storage_adapter=ObjectStorageAdapterConfiguration(
                adapter="fs",
                config=ObjectStorageAdapterFSConfiguration(
                    base_path="storage/datastore"
                ),
            )
        )
    )
    dataset: DatasetServiceConfiguration = DatasetServiceConfiguration(
        dataset_adapter=DatasetAdapterConfiguration(
            adapter="ducklake",
            config=DatasetAdapterDuckLakeConfiguration(
                catalog="sqlite:storage/datasets.sqlite",
                data_path="storage/datasets/",
            ).model_dump(),
        )
    )
    triple_store: TripleStoreServiceConfiguration = TripleStoreServiceConfiguration(
        triple_store_adapter=TripleStoreAdapterConfiguration(
            adapter="oxigraph_embedded",
            config=TripleStoreAdapterOxigraphEmbeddedConfiguration(
                store_path="storage/triplestore/oxigraph",
                graph_base_iri="http://ontology.naas.ai/graph/default",
            ),
        )
    )
    vector_store: VectorStoreServiceConfiguration = VectorStoreServiceConfiguration(
        vector_store_adapter=VectorStoreAdapterConfiguration(
            adapter="qdrant_in_memory",
            config=VectorStoreAdapterQdrantInMemoryConfiguration(
                storage_path="storage/vectorstore/qdrant",
                timeout=300,
            ).model_dump(),
        )
    )
    secret: SecretServiceConfiguration = SecretServiceConfiguration(
        secret_adapters=[
            SecretAdapterConfiguration(
                adapter="dotenv", config=DotenvSecretConfiguration()
            )
        ]
    )
    bus: BusServiceConfiguration = BusServiceConfiguration(
        bus_adapter=BusAdapterConfiguration(
            adapter="python_queue",
            config=BusAdapterPythonQueueConfiguration(
                persistence_path="storage/bus/python_queue.sqlite3",
                journal_mode="WAL",
                busy_timeout_ms=5000,
                poll_interval_seconds=0.05,
                lock_timeout_seconds=1.0,
            ).model_dump(),
        )
    )  # Provide default if not supplied
    kv: KeyValueServiceConfiguration = KeyValueServiceConfiguration(
        kv_adapter=KeyValueAdapterConfiguration(
            adapter="python",
            config=KeyValueAdapterPythonConfiguration(
                persistence_path="storage/kv/python.sqlite3",
                journal_mode="WAL",
                busy_timeout_ms=5000,
            ).model_dump(),
        )
    )
    email: EmailServiceConfiguration = EmailServiceConfiguration(
        email_adapter=EmailAdapterConfiguration(
            adapter="smtp",
            config=EmailAdapterSMTPConfiguration(
                host="localhost",
                port=1025,
                timeout=10,
            ).model_dump(),
        )
    )
    coding_environment: CodingEnvironmentServiceConfiguration = (
        CodingEnvironmentServiceConfiguration(
            coding_environment_adapter=CodingEnvironmentAdapterConfiguration(
                adapter="in_memory",
                config={},
            )
        )
    )
    source_control: SourceControlServiceConfiguration = (
        SourceControlServiceConfiguration(
            source_control_adapter=SourceControlAdapterConfiguration(
                adapter="in_memory",
                config={},
            )
        )
    )
    activity_log: ActivityLogServiceConfiguration = ActivityLogServiceConfiguration(
        activity_log_adapter=ActivityLogAdapterConfiguration(adapter="document")
    )
    event: EventServiceConfiguration = EventServiceConfiguration(
        event_adapter=EventAdapterConfiguration(
            adapter="sqlite",
            config=EventAdapterSqliteConfiguration(),
        )
    )
    model_registry: ModelRegistryServiceConfiguration = (
        ModelRegistryServiceConfiguration()
    )
    cache: CacheServiceConfiguration = CacheServiceConfiguration(
        adapters=[
            CacheAdapterEntry(
                adapter="redis",
                tier=TIER_HOT,
                config=CacheAdapterRedisConfiguration(
                    redis_url="redis://localhost:6379/0",
                    prefix="naas:cache",
                ).model_dump(),
            ),
            CacheAdapterEntry(
                adapter="object_storage",
                tier=TIER_COLD,
                config=CacheAdapterObjectStorageConfiguration(
                    cache_prefix="cache",
                ).model_dump(),
            ),
        ]
    )

    def local_backends(self, owned: Iterable[str]) -> dict[str, str]:
        """For each owned service whose data stays on this host, where it is.

        A deploy that hands over without downtime needs every service the engine
        owns on a shared backend (docs/adr/20261006_single-serving-engine.md).
        ``owned`` names services as in this configuration (``document``, ``kv``,
        ...). The bus is never listed: in NATS mode it is the broker's JetStream.
        """
        found: dict[str, str] = {}
        for name in owned:
            reason = self._local_storage(name)
            if reason:
                found[name] = reason
        return found

    def _local_storage(self, name: str) -> str | None:
        if name == "secret":
            reasons = [a.local_storage() for a in self.secret.secret_adapters]
            return "; ".join(r for r in reasons if r) or None
        if name == "activity_log":
            return self.activity_log.activity_log_adapter.local_storage(
                document=self.document.document_adapter.local_storage()
            )
        if name == "cache":
            object_storage = self.object_storage.object_storage_adapter.local_storage()
            keyvalue = self.kv.kv_adapter.local_storage()
            tiers = [
                (
                    entry.tier,
                    entry.local_storage(
                        object_storage=object_storage, keyvalue=keyvalue
                    ),
                )
                for entry in self.cache.adapters
            ]
            return "; ".join(f"{tier} tier on {r}" for tier, r in tiers if r) or None
        adapters = {
            "coding_environment": self.coding_environment.coding_environment_adapter,
            "dataset": self.dataset.dataset_adapter,
            "document": self.document.document_adapter,
            "email": self.email.email_adapter,
            "event": self.event.event_adapter,
            "kv": self.kv.kv_adapter,
            "object_storage": self.object_storage.object_storage_adapter,
            "source_control": self.source_control.source_control_adapter,
            "triple_store": self.triple_store.triple_store_adapter,
            "vector_store": self.vector_store.vector_store_adapter,
        }
        if name not in adapters:
            return None  # no storage of its own (bus in NATS mode, model registry)
        return adapters[name].local_storage()


class ApiConfiguration(BaseModel):
    title: str = "ABI API"
    description: str = "API for ABI, your Artifical Business Intelligence"
    logo_path: str = "assets/logo.png"
    favicon_path: str = "assets/favicon.ico"
    cors_origins: list[str] = ["http://localhost:9879"]
    reload: bool = True
    host: str = "0.0.0.0"  # nosec B104 - default binds all interfaces
    port: int = 9879


class DiscoveryConfiguration(BaseModel):
    project: str = Field(default="default", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    lease_seconds: float = Field(default=20, ge=1, le=300, allow_inf_nan=False)


class NATSStreamingConfiguration(BaseModel):
    chunk_bytes: int = Field(default=64 * 1024, ge=1024, le=4 * 1024 * 1024)
    idle_seconds: float = Field(default=60, gt=0, allow_inf_nan=False)
    max_sessions: int = Field(default=32, ge=1, le=1024)
    max_upload_bytes: int | None = Field(default=None, gt=0)


class NATSModelStreamingConfiguration(NATSStreamingConfiguration):
    max_upload_bytes: int = Field(default=16 * 1024 * 1024, gt=0)
    max_buffered_upload_bytes: int = Field(default=64 * 1024 * 1024, gt=0)


class NATSModelConfiguration(BaseModel):
    generation_timeout_seconds: float | None = Field(
        default=None, gt=0, allow_inf_nan=False
    )
    streaming: NATSModelStreamingConfiguration = Field(
        default_factory=NATSModelStreamingConfiguration
    )


class NATSRPCOverflowConfiguration(BaseModel):
    """RPC payloads above the broker limit travel as transfer frames instead of
    failing with PAYLOAD_TOO_LARGE (docs/adr/20261003_nats-rpc-overflow.md).

    ``enabled: false`` keeps PAYLOAD_TOO_LARGE for every call over the limit.
    Budgets are per process: parked replies are held in memory, uploaded
    requests are spooled to temporary disk.
    """

    enabled: bool = True
    max_value_bytes: int = Field(default=256 * 1024 * 1024, gt=0)
    max_parked_bytes: int = Field(default=1024 * 1024 * 1024, gt=0)
    max_buffered_upload_bytes: int = Field(default=1024 * 1024 * 1024, gt=0)
    chunk_bytes: int = Field(default=1024 * 1024, ge=1024, le=4 * 1024 * 1024)
    idle_seconds: float = Field(default=60, gt=0, allow_inf_nan=False)
    max_sessions: int = Field(default=64, ge=1, le=1024)


class NATSJobsRetentionConfiguration(BaseModel):
    """How long job hosts keep finished run records (``JobRetention``).

    Active runs are never pruned. Runs that did nothing (``ctx.skip``) go after
    ``skipped_max_age_minutes``; other finished runs after ``max_age_days``,
    and each job keeps at most ``max_runs_per_job``. ``enabled: false`` keeps
    every record.
    """

    enabled: bool = True
    max_age_days: float = Field(default=7, gt=0, allow_inf_nan=False)
    max_runs_per_job: int = Field(default=1000, ge=1)
    skipped_max_age_minutes: float = Field(default=60, gt=0, allow_inf_nan=False)
    interval_minutes: float = Field(default=10, gt=0, allow_inf_nan=False)

    def to_retention(self) -> Any:
        """The SDK ``JobRetention`` (``None`` when disabled)."""
        if not self.enabled:
            return None
        from datetime import timedelta

        from naas_abi_sdk.jobs import JobRetention

        return JobRetention(
            max_age=timedelta(days=self.max_age_days),
            max_runs_per_job=self.max_runs_per_job,
            skipped_max_age=timedelta(minutes=self.skipped_max_age_minutes),
            interval=timedelta(minutes=self.interval_minutes),
        )


class NATSJobsConfiguration(BaseModel):
    """Engine-hosted module jobs (JetStream message schedules, NATS >= 2.14).

    ``enabled: false`` keeps this process from hosting jobs, e.g. a one-off CLI
    engine next to the API engine that hosts them.
    ``interrupt_grace_seconds``: how long a timed-out or cancelled sync job may keep
    running after ``ctx.cancelled`` is set before it is interrupted (``JobInterrupted``
    raised in its thread). ``null`` never interrupts: the run then holds its slot
    until the handler returns.
    """

    enabled: bool = True
    interrupt_grace_seconds: float | None = Field(
        default=5.0, ge=0, allow_inf_nan=False
    )
    retention: NATSJobsRetentionConfiguration = Field(
        default_factory=NATSJobsRetentionConfiguration
    )


class NATSEngineConfiguration(BaseModel):
    """Which engine serves the kernel services (docs/adr/20261006_single-serving-engine.md).

    One engine per NATS account serves them, holding a lease it renews every
    quarter of ``lease_seconds``. Another serving engine fails to start, unless
    its ``rollout_id`` differs from the serving engine's: it then stands by and
    takes over when that engine stops (deploys without downtime), or fails after
    ``standby_timeout_seconds``. ``role: client`` never serves nor hosts jobs:
    scripts that load the engine next to the serving one. ``role: auto`` serves
    when no engine does and is a client otherwise, never a standby: one-off
    engines such as CLI commands, which use it by default.

    ``ABI_ENGINE_ROLE`` and ``ABI_ROLLOUT_ID`` override ``role`` and
    ``rollout_id`` (``resolved``).

    At shutdown the serving engine stops taking requests, then lets the
    transfers, model streams and overflow replies it already serves finish for
    up to ``drain_seconds`` (default: a transfer's idle expiry) before closing
    them. Keep the orchestrator's grace period above it.
    """

    model_config = ConfigDict(extra="forbid")

    role: Literal["serve", "client", "auto"] = "serve"
    rollout_id: str = Field(
        default="", pattern=r"^([A-Za-z0-9_][A-Za-z0-9_.:-]{0,127})?$"
    )
    lease_seconds: float = Field(default=20, ge=1, le=300, allow_inf_nan=False)
    standby_timeout_seconds: float = Field(default=900, gt=0, allow_inf_nan=False)
    drain_seconds: float = Field(default=60, ge=0, allow_inf_nan=False)

    def resolved(self, environ: Mapping[str, str]) -> "NATSEngineConfiguration":
        """These settings with ``ABI_ENGINE_ROLE`` / ``ABI_ROLLOUT_ID`` applied."""
        overrides = {
            field: value
            for field, value in (
                ("role", environ.get("ABI_ENGINE_ROLE", "")),
                ("rollout_id", environ.get("ABI_ROLLOUT_ID", "")),
            )
            if value
        }
        if not overrides:
            return self
        return NATSEngineConfiguration.model_validate(
            {**self.model_dump(), **overrides}
        )

    def timing(self) -> Any:
        """The ownership ``OwnershipTiming`` for these settings."""
        from naas_abi_core.engine.ownership.ownership_service import OwnershipTiming

        return OwnershipTiming(
            lease_seconds=self.lease_seconds,
            standby_timeout_seconds=self.standby_timeout_seconds,
        )


class NATSConfiguration(BaseModel):
    """Cross-cutting NATS exposure config -- not a domain service, so it lives
    at the top level next to ``api``/``deploy``/``global_config``, not nested
    under ``services:``.

    A non-null block enables network domain boundaries. Loaded local owners
    expose endpoints; engine modules and every owner's injected dependencies
    use NATS-backed facades, even when owners share a process. The bus uses
    this broker in NATS mode. Without this block, wiring remains in-process.
    Process-local model registration is available only to modules, never as
    an injected cross-domain dependency. See the network-boundaries ADR.

    Kernel jobs follow the same line. A job that maintains a service's own
    data (dataset compaction) runs on the owner, like its endpoints. A job
    that one domain runs against another (the PostgreSQL event archive writing
    datasets) is a dependency, so it uses the facades.

    A facade call waits ``client_timeout_seconds`` for its reply. Operations
    that can take longer (dataset ``compact``, ``flush``, ``query``) accept a
    deadline per call.

    See docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md
    ("Decisions locked in" -- Stage 1's JWT is deliberately minimal).

    nats:
      nats_url: "nats://127.0.0.1:4222"
      jwt_secret: "{{ secret.NATS_JWT_SECRET }}"
      client_timeout_seconds: 10
    """

    nats_url: str = "nats://127.0.0.1:4222"
    jwt_secret: str
    # How long an engine's facades wait for a reply (calls without their own deadline).
    client_timeout_seconds: float = Field(default=10.0, gt=0, allow_inf_nan=False)
    # Calls each kernel service of this engine handles at once, on as many worker
    # threads. Later calls wait in the broker connection's buffer until their deadline.
    max_concurrent_requests: int = Field(default=64, ge=1, le=4096)
    discovery: DiscoveryConfiguration | None = None
    object_storage_streaming: NATSStreamingConfiguration = Field(
        default_factory=NATSStreamingConfiguration
    )
    models: NATSModelConfiguration = Field(default_factory=NATSModelConfiguration)
    rpc_overflow: NATSRPCOverflowConfiguration = Field(
        default_factory=NATSRPCOverflowConfiguration
    )
    jobs: NATSJobsConfiguration = Field(default_factory=NATSJobsConfiguration)
    engine: NATSEngineConfiguration = Field(default_factory=NATSEngineConfiguration)
    # The broker's HTTP monitoring endpoint (``nats-server -m 8222``), read by the
    # Nexus SysAdmin app (/varz, /connz, /jsz). It has no auth: keep it private.
    monitoring_url: str | None = Field(default=None, pattern=r"^https?://")


class OpencodeProviderConfiguration(BaseModel):
    id: str
    key: str
    type: Literal["api"] = "api"
    metadata: dict[str, str] = Field(default_factory=dict)


class OpencodeConfiguration(BaseModel):
    auth_file_path: str = "~/.local/share/opencode/auth.json"
    providers: list[OpencodeProviderConfiguration] = Field(default_factory=list)


class FirstPassConfiguration(BaseModel):
    """This is a first pass configuration that is used to load the secret service.

    It is used to load the secret service before the other services are loaded.
    This is because the secret service needs to be loaded before the other services
    are loaded to be able to resolve the secrets.
    This is a first pass configuration that is used to load the secret service.
    """

    class FirstPassServicesConfiguration(BaseModel):
        secret: SecretServiceConfiguration

    services: FirstPassServicesConfiguration


class ModuleConfig(BaseModel):
    path: str | None = None
    module: str | None = None
    enabled: bool
    config: dict = {}

    @model_validator(mode="after")
    def validate_path_or_module(self):
        if self.path is None and self.module is None:
            raise ValueError("Either path or module must be provided")

        if self.path is None:
            assert self.module is not None, (
                "module must be provided if path is not provided"
            )
        if self.module is None:
            assert self.path is not None, (
                "path must be provided if module is not provided"
            )
        return self


class GlobalConfig(BaseModel):
    ai_mode: Literal["cloud", "local", "airgap"]
    skip_ontology_loading: bool = False
    public_api_host: str = "localhost:9879"

    @model_validator(mode="after")
    def apply_skip_ontology_loading_override(self) -> Self:
        """Let a launcher opt one process out of the ontology bootstrap.

        Several processes can share a single triple store — `abi dev up` runs
        the api and dagster against the same oxigraph — but the bootstrap is
        the same tens of thousands of triples every time, so having each one
        apply it is pure duplicated work plus cross-process write contention.
        `config.yaml` cannot express that: it is per-project, and these are
        per-process. The env var lets the launcher nominate a single owner.

        Opt-in only. A truthy value forces the skip on; anything else leaves
        the configured value alone, so this can never silently re-enable
        loading for a project that turned it off in `config.yaml`.
        """
        override = os.environ.get("ABI_SKIP_ONTOLOGY_LOADING", "").strip().lower()
        if override in ("1", "true", "yes", "on"):
            self.skip_ontology_loading = True
        return self


# Process-wide cache of the parsed configuration. Without this, every
# caller (api.py at import, Engine.__init__, etc.) constructs a fresh
# Pydantic tree, so runtime mutations (e.g. CORS env injection in api.py)
# only affect one branch and quietly fail to propagate to
# `engine.api_configuration.cors_origins` consumers (Nexus middleware,
# Socket.IO). Module-level rather than a class attr so pydantic doesn't
# claim it as a private model field.
_cached_configuration: "EngineConfiguration | None" = None

# Path to a plain YAML file deep-merged over the selected config after templating,
# e.g. the `nats:` block `abi dev up --with-nats` adds to a project's config.yaml.
CONFIG_OVERLAY_ENV = "ABI_CONFIG_OVERLAY"


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Mappings merge key by key; any other overlay value replaces the base one.

    A mapping naming an ``adapter`` replaces the base one whole: an adapter's
    ``config`` only makes sense for that adapter.
    """
    merged = dict(base)
    for key, value in overlay.items():
        if (
            isinstance(value, dict)
            and "adapter" not in value
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_overlay(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{CONFIG_OVERLAY_ENV} points to a missing file: {path}"
        )
    with open(path, "r") as file:
        overlay = yaml.safe_load(file) or {}
    if not isinstance(overlay, dict):
        raise TypeError(f"{CONFIG_OVERLAY_ENV} must hold a YAML mapping: {path}")
    return overlay


class TelemetryConfiguration(BaseModel):
    """OpenTelemetry tracing (needs ``naas-abi-core[otel]``).

    Spans cover HTTP requests and every NATS call; W3C trace context travels in
    NATS headers so one request is one trace across processes. Exported over
    OTLP/HTTP to ``otlp_endpoint`` (e.g. ``http://jaeger:4318``), or to the
    standard ``OTEL_EXPORTER_OTLP_*`` variables when unset. ``ui_url`` is the
    trace viewer (e.g. Jaeger, ``http://localhost:16686``) the Nexus System app
    links to.
    """

    enabled: bool = False
    otlp_endpoint: str | None = Field(default=None, pattern=r"^https?://")
    service_name: str = "abi-engine"
    sample_ratio: float = Field(default=1.0, ge=0, le=1)
    ui_url: str | None = Field(default=None, pattern=r"^https?://")
    # Where the API reads recent spans for the System app's live traffic
    # (Jaeger's query API, e.g. ``http://jaeger:16686`` inside compose). Defaults to ui_url.
    query_url: str | None = Field(default=None, pattern=r"^https?://")


class EngineConfiguration(BaseModel):
    api: ApiConfiguration

    deploy: DeployConfiguration | None = None

    services: ServicesConfiguration

    global_config: GlobalConfig

    nats: NATSConfiguration | None = None
    telemetry: TelemetryConfiguration = Field(default_factory=TelemetryConfiguration)

    modules: list[ModuleConfig]

    default_agent: str = "naas_abi AbiAgent"

    opencode: OpencodeConfiguration = OpencodeConfiguration()

    # Validated here, used only by `abi dev up --with-nats` (EngineConfiguration_Dev).
    dev: DevConfiguration = Field(default_factory=DevConfiguration)

    def ensure_default_modules(self) -> None:
        default_modules = [
            "naas_abi_core.modules.templatablesparqlquery",
            "naas_abi_core.modules.bfo",
            "naas_abi_core.modules.cco",
        ]
        for module in default_modules:
            if not any(m.path == module or m.module == module for m in self.modules):
                self.modules.append(
                    ModuleConfig(module=module, enabled=True, config={})
                )

    @model_validator(mode="after")
    def validate_modules(self) -> Self:
        self.ensure_default_modules()
        if self.nats is not None:
            bus = self.services.bus.bus_adapter
            if "bus" in self.services.model_fields_set:
                if bus.adapter != "nats_jetstream":
                    raise ValueError(
                        "NATS mode requires services.bus.bus_adapter.adapter=nats_jetstream; remove the explicit bus block to use NATS defaults"
                    )
                if (bus.config or {}).get(
                    "nats_url", "nats://127.0.0.1:4222"
                ) != self.nats.nats_url:
                    raise ValueError("Bus and engine NATS URLs must match")
            remote = [
                entry.adapter == "nats_rpc" for entry in self.services.cache.adapters
            ]
            if any(remote) and not all(remote):
                raise ValueError(
                    "NATS mode cannot mix local and remote cache tiers; configure the full tier topology on its owning engine"
                )
        return self

    @staticmethod
    def _leave_yaml_comments_unrendered(yaml_content: str) -> str:
        """Keep Jinja from evaluating expressions on YAML `#` comment lines.

        Jinja runs before YAML parsing, so `{{ secret.X }}` (or `{% include %}`)
        on a commented-out line would still resolve — and hard-fail when the
        secret is missing and there is no TTY. Wrap those lines in `{% raw %}`
        so they pass through unchanged and stay comments for the YAML parser.

        Only full-line comments (optional space/tab, then `#`) are skipped.
        Inline comments after a value are still rendered.
        """
        masked: list[str] = []
        for line in yaml_content.splitlines(keepends=True):
            newline = ""
            body = line
            if body.endswith("\r\n"):
                newline = "\r\n"
                body = body[:-2]
            elif body.endswith("\n"):
                newline = "\n"
                body = body[:-1]
            if body.lstrip(" \t").startswith("#"):
                # Neutralize a closer that would otherwise terminate the wrap
                # early and leak the rest of the comment into Jinja.
                body = body.replace("{% endraw %}", "{ % endraw %}")
                masked.append("{% raw %}" + body + "{% endraw %}" + newline)
            else:
                masked.append(line)
        return "".join(masked)

    @classmethod
    def _render_yaml_template(
        cls, env: Environment, yaml_content: str, **context
    ) -> str:
        return env.from_string(
            cls._leave_yaml_comments_unrendered(yaml_content)
        ).render(**context)

    @staticmethod
    def _build_jinja_env(base_dir: str | None = None) -> Environment:
        # FileSystemLoader so {% include %} / {% import %} resolve relative to the
        # config file's directory (defaults to CWD when rendering inline content).
        # ChainableUndefined so `{{ secret.X }}` renders to "" instead of raising
        # when no secret context is supplied (used by the bootstrap pass below).
        root = base_dir or os.getcwd()

        class _YamlCommentAwareLoader(FileSystemLoader):
            def get_source(self, environment, template):
                source, filename, uptodate = super().get_source(environment, template)
                return (
                    EngineConfiguration._leave_yaml_comments_unrendered(source),
                    filename,
                    uptodate,
                )

        # autoescape stays off intentionally: this renders YAML config, not HTML.
        # HTML-escaping would corrupt config values (e.g. & < > in secrets/URLs).
        env = Environment(  # nosec B701 - YAML rendering, no HTML/XSS surface
            loader=_YamlCommentAwareLoader(root),
            undefined=ChainableUndefined,
        )

        def load_csv(path: str, **reader_kwargs) -> list[dict]:
            """Parse a CSV file into a list of row dicts, for use in {% for %} loops.

            Path is resolved relative to the config file's directory (same base as
            {% include %}). Extra kwargs are forwarded to csv.DictReader (e.g.
            delimiter=";"). Runs on every render pass, so it must stay side-effect free.
            """
            import csv

            full_path = path if os.path.isabs(path) else os.path.join(root, path)
            with open(full_path, newline="") as csv_file:
                return list(csv.DictReader(csv_file, **reader_kwargs))

        env.globals["load_csv"] = load_csv
        return env

    @classmethod
    def _load_bootstrap_dotenv_adapter_from_yaml_content(
        cls, yaml_content: str, base_dir: str | None = None
    ) -> ISecretAdapter | None:
        # We only need the dotenv path here, which is bootstrap config and cannot
        # itself depend on a secret, so empty-rendered secrets are harmless.
        raw_data = cls.render_without_secrets(yaml_content, base_dir=base_dir)
        if not isinstance(raw_data, dict):
            return None

        services = raw_data.get("services")
        if not isinstance(services, dict):
            return None

        secret = services.get("secret")
        if not isinstance(secret, dict):
            return None

        secret_adapters = secret.get("secret_adapters")
        if not isinstance(secret_adapters, list):
            return None

        for secret_adapter in secret_adapters:
            if not isinstance(secret_adapter, dict):
                continue

            if secret_adapter.get("adapter") != "dotenv":
                continue

            config = secret_adapter.get("config")
            if not isinstance(config, dict):
                config = {}

            path = config.get("path", ".env")
            if not isinstance(path, str) or path.strip() == "":
                raise ValueError(
                    "Invalid dotenv secret adapter path in configuration. "
                    "Expected a non-empty string at services.secret.secret_adapters[].config.path."
                )

            from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
                DotenvSecretSecondaryAdaptor,
            )

            return DotenvSecretSecondaryAdaptor(path=path)

        return None

    @classmethod
    def render_without_secrets(
        cls, yaml_content: str, base_dir: str | None = None
    ) -> Any:
        """The config's YAML data with Jinja rendered and every secret empty.

        Control-flow tags such as {% include %} / {% for %} resolve before the
        YAML is parsed. For bootstrap reads that cannot depend on a secret.
        """
        env = cls._build_jinja_env(base_dir)
        return yaml.safe_load(StringIO(cls._render_yaml_template(env, yaml_content)))

    @classmethod
    def configuration_file(cls) -> str:
        """The file ``load_configuration`` reads: ``config.{ENV}.yaml`` when it
        exists (ENV from the environment, else from the bootstrap dotenv), else
        ``config.yaml``. Relative to the working directory."""
        env = os.getenv("ENV")
        if not env and os.path.exists("config.yaml"):
            with open("config.yaml", "r") as file:
                config_yaml = file.read()

            bootstrap_dotenv_adapter = (
                cls._load_bootstrap_dotenv_adapter_from_yaml_content(config_yaml)
            )
            if bootstrap_dotenv_adapter is not None:
                env_from_bootstrap = bootstrap_dotenv_adapter.get("ENV")
                if env_from_bootstrap is not None:
                    env = str(env_from_bootstrap)

        if env and os.path.exists(f"config.{env}.yaml"):
            return f"config.{env}.yaml"
        if os.path.exists("config.yaml"):
            return "config.yaml"
        raise FileNotFoundError(
            "Configuration file not found. Please create a config.yaml file or config.{env}.yaml file."
        )

    @classmethod
    def from_yaml(
        cls, yaml_path: str, overlay: dict[str, Any] | None = None
    ) -> "EngineConfiguration":
        with open(yaml_path, "r") as file:
            # Resolve {% include %} relative to the config file's directory.
            base_dir = os.path.dirname(os.path.abspath(yaml_path))
            return cls.from_yaml_content(
                file.read(), base_dir=base_dir, overlay=overlay
            )

    @classmethod
    def from_yaml_content(
        cls,
        yaml_content: str,
        base_dir: str | None = None,
        overlay: dict[str, Any] | None = None,
    ) -> "EngineConfiguration":
        env = cls._build_jinja_env(base_dir)
        bootstrap_dotenv_adapter = cls._load_bootstrap_dotenv_adapter_from_yaml_content(
            yaml_content, base_dir=base_dir
        )

        # First we do a pass with the minimal configuration to load the secret service.
        class SecretServiceWrapper:
            secret_service: Secret | None = None
            bootstrap_dotenv_adapter: ISecretAdapter | None = None

            def __init__(
                self,
                secret_service: Secret | None = None,
                bootstrap_dotenv_adapter: ISecretAdapter | None = None,
            ):
                self.secret_service = secret_service
                self.bootstrap_dotenv_adapter = bootstrap_dotenv_adapter

            def __getattr__(self, name):
                if self.secret_service is None:
                    # This rule is used only when doing the first pass configuration to load the secret service.

                    # First priority is to check the environment variables.
                    if name in os.environ:
                        return os.environ.get(name)

                    if self.bootstrap_dotenv_adapter is not None:
                        value = self.bootstrap_dotenv_adapter.get(name)
                        if value is not None:
                            return value

                    return (
                        f"Secret '{name}' not found while loading the secret service. "
                        "Please provide it via the environment variables or configured secret service."
                    )
                elif name in os.environ:
                    return os.environ.get(name)
                secret = self.secret_service.get(name)
                if secret is None:
                    if not sys.stdin.isatty():
                        raise ValueError(
                            f"Secret '{name}' not found and no TTY available to prompt. Please provide it via the configured secret service or environment."
                        )
                    value = Prompt.ask(
                        f"[bold yellow]Secret '{name}' not found.[/bold yellow] Please enter the value for [cyan]{name}[/cyan]",
                        password=False,
                    )
                    self.secret_service.set(name, value)
                    return value
                return secret

        first_pass_data = yaml.safe_load(
            StringIO(
                cls._render_yaml_template(
                    env,
                    yaml_content,
                    secret=SecretServiceWrapper(
                        bootstrap_dotenv_adapter=bootstrap_dotenv_adapter
                    ),
                )
            )
        )

        first_pass_configuration = FirstPassConfiguration(**first_pass_data)
        secret_service = first_pass_configuration.services.secret.load()

        # Here we can now template the yaml by using `yaml_content` and the secret service.
        # Using Jinja2 template engine.

        logger.debug(f"Yaml content: {yaml_content}")

        templated_yaml = cls._render_yaml_template(
            env, yaml_content, secret=SecretServiceWrapper(secret_service)
        )

        data = yaml.safe_load(StringIO(templated_yaml))
        if overlay:
            data = deep_merge(data, overlay)

        # Never log `data`: it holds every rendered secret. The template above
        # is logged before rendering.
        return cls(**data)

    @classmethod
    def reset_configuration_cache(cls) -> None:
        """Forget the cached configuration. Intended for tests."""
        global _cached_configuration
        _cached_configuration = None

    @classmethod
    def load_configuration(
        cls, configuration_yaml: str | None = None
    ) -> "EngineConfiguration":
        # Inline content is for tests — bypass and never cache.
        if configuration_yaml is not None:
            return cls.from_yaml_content(configuration_yaml)

        global _cached_configuration
        if _cached_configuration is not None:
            return _cached_configuration

        config_file = cls.configuration_file()
        overlay = _read_overlay(os.getenv(CONFIG_OVERLAY_ENV))
        logger.debug(
            f"Loading configuration from {config_file}"
            + (f" with overlay {os.getenv(CONFIG_OVERLAY_ENV)}" if overlay else "")
        )

        loaded = cls.from_yaml(config_file, overlay=overlay)
        _cached_configuration = loaded
        return loaded


if __name__ == "__main__":
    config = EngineConfiguration.load_configuration()
    print(config)
