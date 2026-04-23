"""AWS deployment scaffolding + thin Terraform wrappers.

The `abi deploy aws init` command renders the Jinja templates under
`cli/deploy/templates/aws` into `infra/terraform/envs/<env>/` inside the
target project, prompting for project-level values (region, account id,
base domain, etc.).

The `plan`/`apply`/`destroy` subcommands are thin wrappers around the
`terraform` CLI — they resolve the backend config from the values saved
by `init` and run commands inside the env directory.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import click
import naas_abi_cli
from rich.console import Console
from rich.prompt import Confirm, Prompt

from ..utils.Copier import Copier

CONSOLE = Console()

SUPPORTED_ENVS = ("dev", "staging", "prod")
AWS_TEMPLATES_SUBPATH = "cli/deploy/templates/aws"
AWS_INFRA_SUBPATH = "infra/terraform"
AWS_HELM_SUBPATH = "infra/helm/abi"
AWS_STATE_FILE = ".abi-aws.json"

DEFAULT_WORKLOADS = ("abi", "dagster", "mcp-server", "nexus-web", "service-portal")


@dataclass
class AwsDeployConfig:
    project: str
    env: str
    region: str
    account_id: str
    base_domain: str
    github_repo: str
    synapse_enabled: bool
    multi_tenant: bool

    @property
    def state_bucket(self) -> str:
        return f"{self.project}-tfstate-{self.account_id}-{self.region}"

    @property
    def lock_table(self) -> str:
        return f"{self.project}-tflock"


def _state_path(project_path: str) -> Path:
    return Path(project_path) / AWS_STATE_FILE


def _load_state(project_path: str) -> AwsDeployConfig | None:
    path = _state_path(project_path)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return AwsDeployConfig(**data)


def _save_state(project_path: str, config: AwsDeployConfig) -> None:
    _state_path(project_path).write_text(json.dumps(asdict(config), indent=2) + "\n")


def _templates_root() -> Path:
    return Path(naas_abi_cli.__file__).resolve().parent / AWS_TEMPLATES_SUBPATH


def _prompt_config(project_path: str, env: str) -> AwsDeployConfig:
    default_project = Path(project_path).name or "abi"
    project = Prompt.ask("Project name", default=default_project)
    region = Prompt.ask("AWS region", default="us-east-1")
    account_id = Prompt.ask("AWS account ID (12 digits)")
    base_domain = Prompt.ask("Base domain (e.g. abi.example.com)", default=f"{env}.abi.local")
    github_repo = Prompt.ask("GitHub repo (org/name) for OIDC", default="jupyter-naas/abi")
    synapse_enabled = Confirm.ask("Enable Matrix/Synapse?", default=False)
    multi_tenant = Confirm.ask("Multi-tenant (namespace-per-tenant)?", default=True)

    return AwsDeployConfig(
        project=project,
        env=env,
        region=region,
        account_id=account_id,
        base_domain=base_domain,
        github_repo=github_repo,
        synapse_enabled=synapse_enabled,
        multi_tenant=multi_tenant,
    )


def _render_templates(config: AwsDeployConfig, destination: Path) -> None:
    templates_root = _templates_root()
    if not templates_root.exists():
        raise click.ClickException(
            f"AWS deploy templates are missing at {templates_root}. "
            "Ensure the naas-abi-cli package was installed with its template data."
        )

    destination.mkdir(parents=True, exist_ok=True)
    copier = Copier(
        templates_path=str(templates_root),
        destination_path=str(destination),
    )
    copier.copy(values=asdict(config))


def _resolve_env_dir(project_path: str, env: str) -> Path:
    env_dir = Path(project_path) / AWS_INFRA_SUBPATH / "envs" / env
    if not env_dir.exists():
        raise click.ClickException(
            f"Env directory {env_dir} not found — run `abi deploy aws init` first."
        )
    return env_dir


def _run_terraform(env_dir: Path, args: list[str]) -> None:
    terraform = shutil.which("terraform")
    if terraform is None:
        raise click.ClickException("terraform CLI not found in PATH.")
    result = subprocess.run([terraform, *args], cwd=env_dir)
    if result.returncode != 0:
        raise click.ClickException(f"terraform {args[0]} failed (exit {result.returncode}).")


def _terraform_init(env_dir: Path, config: AwsDeployConfig) -> None:
    _run_terraform(
        env_dir,
        [
            "init",
            "-reconfigure",
            f"-backend-config=bucket={config.state_bucket}",
            f"-backend-config=key=envs/{config.env}/terraform.tfstate",
            f"-backend-config=region={config.region}",
            f"-backend-config=dynamodb_table={config.lock_table}",
            "-backend-config=encrypt=true",
        ],
    )


@click.group("aws")
def aws():
    """Deploy ABI on AWS with Terraform."""


@aws.command("init")
@click.option(
    "-e",
    "--env",
    type=click.Choice(SUPPORTED_ENVS),
    default="dev",
    help="Target environment.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite an existing env directory.",
)
def init(env: str, force: bool) -> None:
    """Scaffold the Terraform env directory from templates."""
    project_path = os.getcwd()
    env_dir = Path(project_path) / AWS_INFRA_SUBPATH / "envs" / env

    if env_dir.exists() and not force:
        raise click.ClickException(
            f"{env_dir} already exists. Re-run with --force to overwrite."
        )
    if env_dir.exists() and force:
        shutil.rmtree(env_dir)

    config = _prompt_config(project_path, env)
    _render_templates(config, env_dir)
    _save_state(project_path, config)

    CONSOLE.print(
        f"\n[green]✓[/green] Scaffolded [bold]{env_dir}[/bold].\n"
        f"Next:\n"
        f"  1. cd {AWS_INFRA_SUBPATH}/bootstrap && terraform apply  # once per account\n"
        f"  2. abi deploy aws plan -e {env}\n"
        f"  3. abi deploy aws apply -e {env}\n"
    )


@aws.command("plan")
@click.option("-e", "--env", type=click.Choice(SUPPORTED_ENVS), default="dev")
def plan(env: str) -> None:
    """Run `terraform plan` for the given env."""
    config = _load_state(os.getcwd())
    if config is None:
        raise click.ClickException("No AWS deploy state found — run `abi deploy aws init` first.")
    env_dir = _resolve_env_dir(os.getcwd(), env)
    _terraform_init(env_dir, config)
    _run_terraform(env_dir, ["plan", f"-var=region={config.region}"])


@aws.command("apply")
@click.option("-e", "--env", type=click.Choice(SUPPORTED_ENVS), default="dev")
@click.option("--auto-approve", is_flag=True, default=False)
def apply(env: str, auto_approve: bool) -> None:
    """Run `terraform apply` for the given env."""
    config = _load_state(os.getcwd())
    if config is None:
        raise click.ClickException("No AWS deploy state found — run `abi deploy aws init` first.")
    env_dir = _resolve_env_dir(os.getcwd(), env)
    _terraform_init(env_dir, config)
    args = ["apply", f"-var=region={config.region}"]
    if auto_approve:
        args.append("-auto-approve")
    _run_terraform(env_dir, args)


@aws.command("destroy")
@click.option("-e", "--env", type=click.Choice(SUPPORTED_ENVS), default="dev")
def destroy(env: str) -> None:
    """Run `terraform destroy` for the given env (asks for confirmation)."""
    config = _load_state(os.getcwd())
    if config is None:
        raise click.ClickException("No AWS deploy state found — run `abi deploy aws init` first.")
    if not Confirm.ask(
        f"This will destroy the {env} environment in {config.account_id}/{config.region}. Continue?",
        default=False,
    ):
        raise click.Abort()
    env_dir = _resolve_env_dir(os.getcwd(), env)
    _terraform_init(env_dir, config)
    _run_terraform(env_dir, ["destroy", f"-var=region={config.region}"])


@aws.command("output")
@click.option("-e", "--env", type=click.Choice(SUPPORTED_ENVS), default="dev")
def show_output(env: str) -> None:
    """Run `terraform output -json` for the given env."""
    config = _load_state(os.getcwd())
    if config is None:
        raise click.ClickException("No AWS deploy state found — run `abi deploy aws init` first.")
    env_dir = _resolve_env_dir(os.getcwd(), env)
    _terraform_init(env_dir, config)
    _run_terraform(env_dir, ["output", "-json"])


def _terraform_outputs(env_dir: Path, config: AwsDeployConfig) -> dict:
    terraform = shutil.which("terraform")
    if terraform is None:
        raise click.ClickException("terraform CLI not found in PATH.")
    _terraform_init(env_dir, config)
    result = subprocess.run(
        [terraform, "output", "-json"],
        cwd=env_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise click.ClickException(f"terraform output failed: {result.stderr}")
    return json.loads(result.stdout)


def _require_output(outputs: dict, key: str):
    if key not in outputs:
        raise click.ClickException(
            f"Terraform output '{key}' is missing — apply the stack first."
        )
    return outputs[key]["value"]


def _ecr_repo_url(outputs: dict, name: str) -> str:
    repos = _require_output(outputs, "ecr_repositories")
    if name not in repos:
        raise click.ClickException(f"ECR repository '{name}' not in terraform outputs.")
    return repos[name]


@aws.command("kubeconfig")
@click.option("-e", "--env", type=click.Choice(SUPPORTED_ENVS), default="dev")
def kubeconfig(env: str) -> None:
    """Update local kubeconfig to point at the EKS cluster."""
    config = _load_state(os.getcwd())
    if config is None:
        raise click.ClickException("No AWS deploy state found — run `abi deploy aws init` first.")

    env_dir = _resolve_env_dir(os.getcwd(), env)
    outputs = _terraform_outputs(env_dir, config)
    cluster_name = _require_output(outputs, "cluster_name")

    aws_cli = shutil.which("aws")
    if aws_cli is None:
        raise click.ClickException("aws CLI not found in PATH.")

    result = subprocess.run(
        [aws_cli, "eks", "update-kubeconfig", "--name", cluster_name, "--region", config.region],
    )
    if result.returncode != 0:
        raise click.ClickException(f"aws eks update-kubeconfig failed (exit {result.returncode}).")


def _render_values_from_outputs(config: AwsDeployConfig, outputs: dict, image_tag: str) -> dict:
    """Build the helm -f JSON values doc from terraform outputs."""
    return {
        "global": {
            "project": config.project,
            "env": config.env,
            "awsAccountId": config.account_id,
            "awsRegion": config.region,
            "imageTag": image_tag,
        },
        "externalSecrets": {
            "serviceAccountRoleArn": _require_output(outputs, "tenant_secrets_role_arn"),
            "secrets": {
                "rds": f"{config.project}/{config.env}/rds/main",
                "redis": f"{config.project}/{config.env}/redis",
                "rabbitmq": f"{config.project}/{config.env}/rabbitmq",
            },
        },
        "abiApi": {
            "image": {"repository": _ecr_repo_url(outputs, "abi")},
            "serviceAccount": {"roleArn": _require_output(outputs, "abi_api_role_arn")},
            "extraEnvFrom": [
                {"secretRef": {"name": "abi-rds"}},
                {"secretRef": {"name": "abi-redis"}},
                {"secretRef": {"name": "abi-rabbitmq"}},
            ],
        },
        "dagster": {
            "image": {"repository": _ecr_repo_url(outputs, "dagster")},
            "extraEnvFrom": [{"secretRef": {"name": "abi-rds"}}],
        },
        "mcpServer": {"image": {"repository": _ecr_repo_url(outputs, "mcp-server")}},
        "nexusWeb": {
            "image": {"repository": _ecr_repo_url(outputs, "nexus-web")},
            "env": {"NEXUS_API_URL": "http://abi-api:9879"},
        },
        "servicePortal": {"image": {"repository": _ecr_repo_url(outputs, "service-portal")}},
        "synapse": {"enabled": config.synapse_enabled},
    }


@aws.command("deploy-apps")
@click.option("-e", "--env", type=click.Choice(SUPPORTED_ENVS), default="dev")
@click.option("--image-tag", default="latest", help="Image tag to deploy (must exist in ECR).")
@click.option("--namespace", default="abi", help="Kubernetes namespace (tenant) for this release.")
@click.option(
    "--release-name",
    default=None,
    help="Helm release name (defaults to the namespace).",
)
@click.option("--dry-run", is_flag=True, default=False, help="Render manifests without applying.")
def deploy_apps(
    env: str,
    image_tag: str,
    namespace: str,
    release_name: str | None,
    dry_run: bool,
) -> None:
    """Helm-install the umbrella chart using terraform outputs for config."""
    config = _load_state(os.getcwd())
    if config is None:
        raise click.ClickException("No AWS deploy state found — run `abi deploy aws init` first.")

    helm = shutil.which("helm")
    if helm is None:
        raise click.ClickException("helm CLI not found in PATH.")

    chart_path = Path(os.getcwd()) / AWS_HELM_SUBPATH
    if not chart_path.exists():
        raise click.ClickException(
            f"Helm chart not found at {chart_path}. "
            "Check out the repo in a state that includes infra/helm/abi."
        )

    env_dir = _resolve_env_dir(os.getcwd(), env)
    outputs = _terraform_outputs(env_dir, config)
    values = _render_values_from_outputs(config, outputs, image_tag)
    values["namespace"] = {"create": True, "name": namespace}

    values_file = Path(os.getcwd()) / f".abi-helm-values.{env}.json"
    values_file.write_text(json.dumps(values, indent=2))

    release = release_name or namespace
    args = [
        helm, "upgrade", "--install", release, str(chart_path),
        "--namespace", namespace,
        "--create-namespace",
        "-f", str(values_file),
        "--wait", "--timeout", "10m",
    ]
    if dry_run:
        args.insert(2, "--dry-run")

    CONSOLE.print(f"[cyan]Running:[/cyan] {' '.join(args)}")
    result = subprocess.run(args)
    if result.returncode != 0:
        raise click.ClickException(f"helm upgrade --install failed (exit {result.returncode}).")

    CONSOLE.print(f"\n[green]✓[/green] {release} deployed to namespace '{namespace}'.\n")


@aws.command("ecr-login")
@click.option("-e", "--env", type=click.Choice(SUPPORTED_ENVS), default="dev")
def ecr_login(env: str) -> None:
    """`docker login` to the account's ECR registry."""
    config = _load_state(os.getcwd())
    if config is None:
        raise click.ClickException("No AWS deploy state found — run `abi deploy aws init` first.")
    registry = f"{config.account_id}.dkr.ecr.{config.region}.amazonaws.com"
    aws_cli = shutil.which("aws") or "aws"
    docker = shutil.which("docker") or "docker"
    pwd = subprocess.run(
        [aws_cli, "ecr", "get-login-password", "--region", config.region],
        capture_output=True,
        text=True,
    )
    if pwd.returncode != 0:
        raise click.ClickException(f"aws ecr get-login-password failed: {pwd.stderr}")
    login = subprocess.run(
        [docker, "login", "--username", "AWS", "--password-stdin", registry],
        input=pwd.stdout,
        text=True,
    )
    if login.returncode != 0:
        raise click.ClickException("ECR login failed.")


@aws.command("build-push")
@click.option("-e", "--env", type=click.Choice(SUPPORTED_ENVS), default="dev")
@click.option("--image-tag", default="latest")
@click.option(
    "--only",
    type=click.Choice(DEFAULT_WORKLOADS),
    multiple=True,
    help="Build only these workloads (default: all).",
)
def build_push(env: str, image_tag: str, only: tuple[str, ...]) -> None:
    """Build & push Docker images for all workloads to ECR.

    Assumes each workload has a Dockerfile under a conventional path. Today
    only `abi` and `nexus-web` are known to exist in the repo — others
    must be wired as they're added.
    """
    config = _load_state(os.getcwd())
    if config is None:
        raise click.ClickException("No AWS deploy state found — run `abi deploy aws init` first.")

    contexts = {
        "abi": (".", "docker/images/Dockerfile"),
        "nexus-web": (
            "libs/naas-abi/naas_abi/apps/nexus",
            "libs/naas-abi/naas_abi/apps/nexus/Dockerfile",
        ),
    }
    targets = only or tuple(contexts.keys())
    registry = f"{config.account_id}.dkr.ecr.{config.region}.amazonaws.com"
    docker = shutil.which("docker") or "docker"

    for name in targets:
        if name not in contexts:
            CONSOLE.print(f"[yellow]skip[/yellow] {name}: no known Dockerfile context")
            continue
        ctx, dockerfile = contexts[name]
        image = f"{registry}/{config.project}/{name}:{image_tag}"
        CONSOLE.print(f"[cyan]build[/cyan] {image}")
        subprocess.run(
            [docker, "buildx", "build", "--platform", "linux/amd64",
             "-f", dockerfile, "-t", image, "--push", ctx],
            check=False,
        )
