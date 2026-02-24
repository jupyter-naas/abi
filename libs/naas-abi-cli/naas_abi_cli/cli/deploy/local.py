import os
import shutil
from ipaddress import ip_address
from uuid import uuid4

import naas_abi_cli
from rich.prompt import Prompt

from ..utils.Copier import Copier

LOCAL_ENV_MARKER = "# Added by abi deploy local command execution"
HEADSCALE_SERVICE_MARKER = "  headscale:"

DEFAULT_ENV_VALUES: dict[str, str] = {
    "POSTGRES_USER": "abi",
    "POSTGRES_DB": "abi",
    "POSTGRES_HOST": "postgres",
    "POSTGRES_PORT": "5432",
    "QDRANT_HOST": "qdrant",
    "QDRANT_PORT": "6333",
    "REDIS_PORT": "6379",
    "MINIO_HOST": "minio",
    "MINIO_PORT": "9000",
    "MINIO_ROOT_USER": "abi",
    "ABI_HOST": "abi",
    "PUBLIC_WEB_HOST": "nexus.localhost",
    "PUBLIC_API_HOST": "api.localhost",
    "RABBITMQ_USER": "abi",
    "NEXUS_WEB_IMAGE": "ghcr.io/jupyter-naas/nexus-web",
    "NEXUS_WEB_TAG": "latest",
    "NEXUS_WEB_PORT": "3042",
    "HEADSCALE_SERVER_URL": "localhost",
    "HEADSCALE_SERVER_PORT": "8083",
    "HEADSCALE_METRICS_PORT": "9090",
    "HEADSCALE_GRPC_PORT": "50443",
    "HEADSCALE_INTERNAL_DOMAIN": "tail.local",
    "HEADSCALE_ACME_EMAIL": "",
}

RANDOM_ENV_KEYS: tuple[str, ...] = (
    "POSTGRES_PASSWORD",
    "MINIO_ROOT_PASSWORD",
    "RABBITMQ_PASSWORD",
    "FUSEKI_ADMIN_PASSWORD",
)

HEADSCALE_DOCKER_COMPOSE_SNIPPET = """

  headscale:
    image: docker.io/headscale/headscale:stable
    pull_policy: always
    restart: unless-stopped
    command: ["headscale", "serve"]
    ports:
      - ${HEADSCALE_SERVER_PORT}:8080
      - ${HEADSCALE_METRICS_PORT}:9090
      - ${HEADSCALE_GRPC_PORT}:50443
    volumes:
      - ./.deploy/docker/headscale/config.yaml:/etc/headscale/config.yaml:ro
      - ./.deploy/docker/headscale/extra-records.json:/var/lib/headscale/extra-records.json:ro
      - headscale_data:/var/lib/headscale
      - headscale_run:/var/run/headscale
    healthcheck:
      test: ["CMD", "headscale", "health"]
      interval: 15s
      timeout: 5s
      retries: 10
      start_period: 30s
    networks:
      - abi-network
"""


def _copy_headscale_templates(deploy_path: str) -> None:
    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__),
            "cli/deploy/templates/local/docker/headscale",
        ),
        destination_path=os.path.join(deploy_path, "docker/headscale"),
    )
    copier.copy(values=DEFAULT_ENV_VALUES)


def _ensure_headscale_service(docker_compose_target_path: str) -> None:
    if not os.path.exists(docker_compose_target_path):
        return

    with open(docker_compose_target_path, "r", encoding="utf-8") as compose_file:
        compose_content = compose_file.read()

    if HEADSCALE_SERVICE_MARKER in compose_content:
        return

    volumes_anchor = "\nvolumes:\n"
    if volumes_anchor not in compose_content:
        raise ValueError(
            "Unable to add headscale service: docker compose volumes section missing"
        )

    compose_with_service = compose_content.replace(
        volumes_anchor,
        HEADSCALE_DOCKER_COMPOSE_SNIPPET + volumes_anchor,
        1,
    )

    if "  headscale_data:" not in compose_with_service:
        compose_with_service = compose_with_service.replace(
            "  qdrant_storage: # Qdrant vector store data\n",
            "  qdrant_storage: # Qdrant vector store data\n"
            "  headscale_data: # Headscale state and sqlite database\n"
            "  headscale_run:  # Headscale unix socket runtime data\n",
            1,
        )

    with open(docker_compose_target_path, "w", encoding="utf-8") as compose_file:
        compose_file.write(compose_with_service)


def _split_host_and_port(host: str) -> tuple[str, str | None]:
    normalized_host = host.strip()

    if normalized_host.startswith("["):
        bracket_end = normalized_host.find("]")
        if bracket_end == -1:
            return normalized_host, None

        host_part = normalized_host[1:bracket_end]
        remainder = normalized_host[bracket_end + 1 :]
        if remainder.startswith(":") and remainder[1:].isdigit():
            return host_part, remainder[1:]
        return host_part, None

    host_parts = normalized_host.rsplit(":", 1)
    if len(host_parts) == 2 and host_parts[1].isdigit() and ":" not in host_parts[0]:
        return host_parts[0], host_parts[1]

    return normalized_host, None


def _is_localhost_or_ip(host: str) -> bool:
    host_without_port, _ = _split_host_and_port(host)

    if host_without_port.lower() == "localhost":
        return True

    try:
        ip_address(host_without_port)
        return True
    except ValueError:
        return False


def _build_nexus_api_url(
    public_api_host: str,
    public_api_scheme: str | None = None,
    abi_port: str = "9879",
) -> str:
    scheme = public_api_scheme
    if scheme is None:
        scheme = "http" if _is_localhost_or_ip(public_api_host) else "https"

    _, explicit_port = _split_host_and_port(public_api_host)

    if explicit_port is not None:
        return f"{scheme}://{public_api_host}"

    if _is_localhost_or_ip(public_api_host):
        return f"{scheme}://{public_api_host}:{abi_port}"

    return f"{scheme}://{public_api_host}"


def _ensure_env_var(env_path: str, key: str, value: str) -> None:
    existing_content = ""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as env_file:
            existing_content = env_file.read()

    for line in existing_content.splitlines():
        if line.strip().startswith(f"{key}="):
            return

    with open(env_path, "a", encoding="utf-8") as env_file:
        if existing_content and not existing_content.endswith("\n"):
            env_file.write("\n")
        env_file.write(f"{key}={value}\n")


def _get_env_var(env_path: str, key: str) -> str | None:
    if not os.path.exists(env_path):
        return None

    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not stripped.startswith(f"{key}="):
                continue
            return stripped.split("=", 1)[1]

    return None


def _append_local_env_once(source_env_path: str, destination_env_path: str) -> None:
    with open(source_env_path, "r", encoding="utf-8") as source_file:
        source_content = source_file.read()

    if source_content.strip() == "":
        open(destination_env_path, "a", encoding="utf-8").close()
        return

    current_content = ""
    if os.path.exists(destination_env_path):
        with open(destination_env_path, "r", encoding="utf-8") as destination_file:
            current_content = destination_file.read()

    if LOCAL_ENV_MARKER in current_content:
        return

    with open(destination_env_path, "a", encoding="utf-8") as destination_file:
        if current_content and not current_content.endswith("\n"):
            destination_file.write("\n")
        destination_file.write(source_content)


def setup_local_deploy(
    project_path: str,
    include_headscale: bool = False,
    public_web_host: str | None = None,
    public_api_host: str | None = None,
) -> None:
    project_path = os.path.abspath(os.path.expanduser(project_path))

    deploy_path = os.path.join(project_path, ".deploy")
    docker_compose_template_path = os.path.join(deploy_path, "docker-compose.yml")
    docker_compose_target_path = os.path.join(project_path, "docker-compose.yml")
    local_env_template_path = os.path.join(deploy_path, ".env")
    local_env_target_path = os.path.join(project_path, ".env")

    if public_web_host is None:
        public_web_host = Prompt.ask(
            f"Public web host (example: {DEFAULT_ENV_VALUES['PUBLIC_WEB_HOST']})",
            default=DEFAULT_ENV_VALUES["PUBLIC_WEB_HOST"],
        )
    if public_api_host is None:
        public_api_host = Prompt.ask(
            f"Public API host (example: {DEFAULT_ENV_VALUES['PUBLIC_API_HOST']})",
            default=DEFAULT_ENV_VALUES["PUBLIC_API_HOST"],
        )
    nexus_api_url = _build_nexus_api_url(public_api_host=public_api_host)

    if not os.path.exists(deploy_path):
        os.makedirs(deploy_path, exist_ok=False)

        copier = Copier(
            templates_path=os.path.join(
                os.path.dirname(naas_abi_cli.__file__), "cli/deploy/templates/local"
            ),
            destination_path=deploy_path,
        )
        copier.copy(
            values={
                **DEFAULT_ENV_VALUES,
                "PUBLIC_WEB_HOST": public_web_host,
                "PUBLIC_API_HOST": public_api_host,
                "NEXUS_API_URL": nexus_api_url,
                "INCLUDE_HEADSCALE": include_headscale,
                "POSTGRES_PASSWORD": str(uuid4()),
                "MINIO_ROOT_PASSWORD": str(uuid4()),
                "RABBITMQ_PASSWORD": str(uuid4()),
                "FUSEKI_ADMIN_PASSWORD": str(uuid4()),
            }
        )

    if os.path.exists(docker_compose_template_path):
        if os.path.exists(docker_compose_target_path):
            os.remove(docker_compose_template_path)
        else:
            shutil.move(docker_compose_template_path, docker_compose_target_path)

    if os.path.exists(local_env_template_path):
        _append_local_env_once(local_env_template_path, local_env_target_path)
        os.remove(local_env_template_path)

    for key, value in DEFAULT_ENV_VALUES.items():
        if not include_headscale and key.startswith("HEADSCALE_"):
            continue
        if key in {"PUBLIC_WEB_HOST", "PUBLIC_API_HOST"}:
            continue
        _ensure_env_var(local_env_target_path, key, value)

    _ensure_env_var(local_env_target_path, "PUBLIC_WEB_HOST", public_web_host)
    _ensure_env_var(local_env_target_path, "PUBLIC_API_HOST", public_api_host)

    for key in RANDOM_ENV_KEYS:
        _ensure_env_var(local_env_target_path, key, str(uuid4()))

    persisted_public_api_host = (
        _get_env_var(local_env_target_path, "PUBLIC_API_HOST")
        or DEFAULT_ENV_VALUES["PUBLIC_API_HOST"]
    )
    public_api_scheme = _get_env_var(local_env_target_path, "PUBLIC_API_SCHEME")
    _ensure_env_var(
        local_env_target_path,
        "NEXUS_API_URL",
        _build_nexus_api_url(
            public_api_host=persisted_public_api_host,
            public_api_scheme=public_api_scheme,
        ),
    )

    if include_headscale:
        _copy_headscale_templates(deploy_path)
        _ensure_headscale_service(docker_compose_target_path)
