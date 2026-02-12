import os
import shutil
from uuid import uuid4

import naas_abi_cli

from ..utils.Copier import Copier

LOCAL_ENV_MARKER = "# Added by abi deploy local command execution"


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


def setup_local_deploy(project_path: str) -> None:
    project_path = os.path.abspath(os.path.expanduser(project_path))

    deploy_path = os.path.join(project_path, ".deploy")
    docker_compose_template_path = os.path.join(deploy_path, "docker-compose.yml")
    docker_compose_target_path = os.path.join(project_path, "docker-compose.yml")
    local_env_template_path = os.path.join(deploy_path, ".env")
    local_env_target_path = os.path.join(project_path, ".env")

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
                "POSTGRES_USER": "abi",
                "POSTGRES_PASSWORD": str(uuid4()),
                "POSTGRES_DB": "abi",
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

    _ensure_env_var(local_env_target_path, "FUSEKI_ADMIN_PASSWORD", str(uuid4()))
