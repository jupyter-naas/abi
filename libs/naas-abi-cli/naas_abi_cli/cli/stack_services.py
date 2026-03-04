import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

from .stack_runtime import ComposeServiceState


ABI_REQUIRED_URL = "http://127.0.0.1:9879"


@dataclass(frozen=True)
class ServiceDefinition:
    key: str
    display_name: str
    category: str
    description: str
    urls: tuple[str, ...] = ()
    tcp_targets: tuple[tuple[str, int], ...] = ()
    is_one_shot: bool = False


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    source: str
    detail: str


SERVICE_CATALOG: dict[str, ServiceDefinition] = {
    "abi": ServiceDefinition(
        key="abi",
        display_name="ABI API",
        category="Essentials",
        description="Core ABI service and APIs.",
        urls=(ABI_REQUIRED_URL, "http://127.0.0.1:8501"),
    ),
    "mcp-server": ServiceDefinition(
        key="mcp-server",
        display_name="MCP Server",
        category="Essentials",
        description="Model context protocol server.",
        urls=("http://127.0.0.1:8000",),
    ),
    "postgres": ServiceDefinition(
        key="postgres",
        display_name="PostgreSQL",
        category="Databases",
        description="Agent memory database.",
        tcp_targets=(("127.0.0.1", 5432),),
    ),
    "fuseki": ServiceDefinition(
        key="fuseki",
        display_name="Fuseki",
        category="Databases",
        description="RDF triple store.",
        urls=("http://127.0.0.1:3030/$/ping",),
    ),
    "yasgui": ServiceDefinition(
        key="yasgui",
        display_name="YasGUI",
        category="Databases",
        description="SPARQL query UI.",
        urls=("http://127.0.0.1:3000",),
    ),
    "dagster": ServiceDefinition(
        key="dagster",
        display_name="Dagster",
        category="Orchestration",
        description="Pipeline orchestration UI.",
        urls=("http://127.0.0.1:3001",),
    ),
    "minio": ServiceDefinition(
        key="minio",
        display_name="MinIO",
        category="Storage",
        description="S3-compatible object storage.",
        urls=("http://127.0.0.1:9001",),
        tcp_targets=(("127.0.0.1", 9000),),
    ),
    "minio-init": ServiceDefinition(
        key="minio-init",
        display_name="MinIO Init",
        category="Storage",
        description="Initialization container for MinIO buckets.",
        is_one_shot=True,
    ),
    "rabbitmq": ServiceDefinition(
        key="rabbitmq",
        display_name="RabbitMQ",
        category="Messaging",
        description="Message bus and management UI.",
        urls=("http://127.0.0.1:15672",),
        tcp_targets=(("127.0.0.1", 5672),),
    ),
    "redis": ServiceDefinition(
        key="redis",
        display_name="Redis",
        category="Messaging",
        description="In-memory cache and broker.",
        tcp_targets=(("127.0.0.1", 6379),),
    ),
    "redis-commander": ServiceDefinition(
        key="redis-commander",
        display_name="Redis Commander",
        category="Messaging",
        description="Redis management UI.",
        urls=("http://127.0.0.1:8082",),
    ),
    "matrix": ServiceDefinition(
        key="matrix",
        display_name="Matrix Synapse",
        category="Matrix",
        description="Federated messaging homeserver.",
        urls=("http://127.0.0.1:8008/_matrix/client/versions",),
        tcp_targets=(("127.0.0.1", 8448),),
    ),
    "element-web": ServiceDefinition(
        key="element-web",
        display_name="Element Web",
        category="Matrix",
        description="Matrix web client.",
        urls=("http://127.0.0.1:8081",),
    ),
    "service-portal": ServiceDefinition(
        key="service-portal",
        display_name="Service Portal",
        category="Essentials",
        description="Gateway page for local services.",
        urls=("http://127.0.0.1:8080",),
    ),
    "qdrant": ServiceDefinition(
        key="qdrant",
        display_name="Qdrant",
        category="Databases",
        description="Vector database.",
        urls=("http://127.0.0.1:6333/collections",),
        tcp_targets=(("127.0.0.1", 6334),),
    ),
}


def _check_http(url: str, timeout: float = 1.5) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            return status < 500, f"HTTP {status}"
    except urllib.error.HTTPError as error:
        if error.code < 500:
            return True, f"HTTP {error.code}"
        return False, f"HTTP {error.code}"
    except (urllib.error.URLError, TimeoutError) as error:
        return False, str(error)


def _check_tcp(host: str, port: int, timeout: float = 1.2) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"TCP {host}:{port}"
    except OSError as error:
        return False, str(error)


def evaluate_service_readiness(
    service_name: str,
    state: ComposeServiceState | None,
    http_timeout: float = 1.5,
    tcp_timeout: float = 1.2,
) -> ReadinessResult:
    if state is None:
        return ReadinessResult(False, "compose", "Container not created")

    if state.health == "unhealthy":
        return ReadinessResult(False, "docker-health", "Container reports unhealthy")

    service = SERVICE_CATALOG.get(service_name)
    if service and service.is_one_shot:
        if state.state == "exited" and state.exit_code == 0:
            return ReadinessResult(True, "compose", "One-shot init completed")
        return ReadinessResult(False, "compose", "One-shot init not completed")

    if service_name == "abi":
        if state.state != "running":
            return ReadinessResult(
                False, "compose", f"Container state is {state.state}"
            )

        ready, detail = _check_http(ABI_REQUIRED_URL, timeout=http_timeout)
        if ready:
            return ReadinessResult(True, "http", detail)
        return ReadinessResult(False, "http", detail)

    if state.health == "healthy":
        return ReadinessResult(True, "docker-health", "Container reports healthy")

    if state.state != "running":
        return ReadinessResult(False, "compose", f"Container state is {state.state}")

    if service:
        for url in service.urls:
            ready, detail = _check_http(url, timeout=http_timeout)
            if ready:
                return ReadinessResult(True, "http", detail)

        for host, port in service.tcp_targets:
            ready, detail = _check_tcp(host, port, timeout=tcp_timeout)
            if ready:
                return ReadinessResult(True, "tcp", detail)

    return ReadinessResult(True, "compose", "Container is running")
