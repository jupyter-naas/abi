import os
import shlex
import shutil
import subprocess
import sys

import click

import naas_abi_cli
from naas_abi_cli.cli.deploy.local import _build_hosts_from_domain, setup_local_deploy
from naas_abi_cli.cli.utils.Copier import Copier

from .module import new_module
from .new import new
from .utils import to_kebab_case, to_pascal_case, to_snake_case

ABI_SUBMODULE_URL = "https://github.com/jupyter-naas/abi.git"
ABI_SUBMODULE_PATH = ".abi"


def _add_abi_submodule(project_path: str) -> bool:
    """Add the upstream ABI repo as a git submodule at `.abi/`.

    Agents working in the scaffolded project can then read framework
    docs/source locally instead of fetching them over the network, and
    `pyproject.toml` can point uv at `.abi/libs/*` instead of PyPI.

    Failures are non-fatal — the project is still usable without it, resolving
    the framework from PyPI. Returns whether `.abi/libs` is actually usable,
    which is what decides how `pyproject.toml` is rendered; claiming success we
    do not have would leave uv pointed at paths that don't exist.
    """
    if shutil.which("git") is None:
        click.secho(
            "  git not found on PATH; skipping .abi submodule. "
            "Add it later with: git submodule add "
            f"{ABI_SUBMODULE_URL} {ABI_SUBMODULE_PATH}",
            fg="yellow",
        )
        return False

    if not os.path.isdir(os.path.join(project_path, ".git")):
        subprocess.run(["git", "init", "-q"], cwd=project_path, check=True)

    try:
        subprocess.run(
            [
                "git",
                "submodule",
                "add",
                "--depth",
                "1",
                ABI_SUBMODULE_URL,
                ABI_SUBMODULE_PATH,
            ],
            cwd=project_path,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        click.secho(
            f"  failed to add .abi submodule ({e}); continuing without it. "
            "Add it later with: git submodule add "
            f"{ABI_SUBMODULE_URL} {ABI_SUBMODULE_PATH}",
            fg="yellow",
        )
        return False

    # A clone that succeeded but landed an unexpected layout is still unusable
    # as a dependency source, so check for the directory uv will be told about.
    return os.path.isdir(os.path.join(project_path, ABI_SUBMODULE_PATH, "libs"))


def _cd_argument(project_path: str) -> str:
    """The shortest `cd` target that gets the caller from their CWD to the project.

    `abi` runs as a child process, so it cannot change the calling shell's
    working directory — the best it can do is hand back a line to paste. A
    relative path is what the caller would have typed themselves, so prefer it
    when the project sits under the CWD; anything else (a sibling, an absolute
    `project-path` argument) is clearer spelled out in full.
    """
    try:
        relative = os.path.relpath(project_path, os.getcwd())
    except ValueError:
        # Windows: no relative path exists across drives.
        return shlex.quote(project_path)

    # `..`-prefixed paths are not more readable than the absolute one.
    if relative == os.curdir or relative.startswith(os.pardir):
        return shlex.quote(project_path)
    return shlex.quote(relative)


def _print_next_steps(project_path: str) -> None:
    """Report where the project landed and how to start it."""
    click.echo()
    click.secho(f"✓ Project created at {project_path}", fg="green", bold=True)
    click.echo()
    click.secho("Next steps:", bold=True)
    click.echo(f"  cd {_cd_argument(project_path)}")
    click.echo("  abi dev up")
    click.echo()


@new.command("project")
@click.argument("project-name", required=False, default=None)
@click.argument("project-path", required=False, default=None)
@click.option(
    "--with-local-deploy/--without-local-deploy",
    default=True,
    help="Generate local docker-compose and deployment scaffolding (default: enabled).",
)
@click.option(
    "--with-headscale/--without-headscale",
    default=False,
    help="Include a headscale service in local deploy scaffolding (default: disabled).",
)
@click.option(
    "--with-coding/--without-coding",
    default=False,
    help=(
        "Include coding workspaces (Coder + Forgejo + Actions CI) in local "
        "deploy scaffolding (default: disabled)."
    ),
)
@click.option(
    "--with-abi-submodule/--without-abi-submodule",
    default=True,
    help=(
        "Add jupyter-naas/abi as a git submodule at .abi/ so agents can "
        "locate framework source and docs locally (default: enabled)."
    ),
)
@click.option(
    "--domain",
    "base_domain",
    prompt="Base domain",
    default="localhost",
    show_default=True,
    help=(
        "Base domain for the project (sets BASE_DOMAIN, with PUBLIC_WEB_HOST "
        "and PUBLIC_API_HOST derived as nexus.<domain> and api.<domain>). "
        "Threaded into local deploy when --with-local-deploy is enabled."
    ),
)
def new_project(
    project_name: str | None,
    project_path: str | None,
    with_local_deploy: bool,
    with_headscale: bool,
    with_coding: bool,
    with_abi_submodule: bool,
    base_domain: str,
):
    # Defaults must be evaluated at runtime so they reflect the caller's CWD.
    if project_name is None:
        project_name = os.path.basename(os.getcwd())
    project_name = to_kebab_case(project_name)
    if project_path is None:
        project_path = os.getcwd()
    # Resolve relative segments (., ..) and user home (~) to a normalized absolute path.
    project_path = os.path.abspath(os.path.expanduser(project_path))

    # Ensure the last path component matches the project name, not just the suffix.
    if os.path.basename(os.path.normpath(project_path)) != project_name:
        project_path = os.path.join(project_path, project_name)

    if not os.path.exists(project_path):
        os.makedirs(project_path, exist_ok=True)
    elif len(os.listdir(project_path)) > 0:
        print(f"Folder {project_path} already exists and is not empty.")
        sys.exit(1)

    # Added before the templates are rendered: whether `.abi/libs` exists is
    # what decides if `pyproject.toml` resolves the framework from source or
    # from PyPI, and that has to be baked into the file we are about to write.
    abi_submodule_added = with_abi_submodule and _add_abi_submodule(project_path)

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/project"
        ),
        destination_path=project_path,
    )
    hosts = _build_hosts_from_domain(base_domain)
    copier.copy(
        values={
            "project_name": project_name,
            "project_name_snake": to_snake_case(project_name),
            "project_name_pascal": to_pascal_case(project_name),
            "base_domain": base_domain,
            "public_web_host": hosts["PUBLIC_WEB_HOST"],
            "public_api_host": hosts["PUBLIC_API_HOST"],
            # When the coding stack is provisioned (`--with-coding`), the config
            # enables the "code" feature flag for workspace admins by default.
            "include_coding": with_coding,
            "use_local_abi_sources": abi_submodule_added,
        }
    )

    # Calling new_module to create the module in the src folder
    new_module(project_name, os.path.join(project_path, "src"), quiet=True)

    if with_local_deploy:
        setup_local_deploy(
            project_path,
            include_headscale=with_headscale,
            include_coding=with_coding,
            base_domain=base_domain,
        )

    # Run dependency install without shell to avoid quoting issues on paths with spaces.
    # ai-openrouter is the marketplace extra the generated config.yaml enables:
    # one gateway key serves both defaults — Gemma 4 for chat and
    # text-embedding-3-small for embeddings.
    subprocess.run(
        [
            "uv",
            "add",
            "naas-abi-core[all]",
            "naas-abi-marketplace[ai-openrouter]",
            "naas-abi",
            "naas-abi-cli",
        ],
        cwd=project_path,
        check=True,
    )

    subprocess.run(
        ["uv", "run", "abi", "config", "validate"],
        cwd=project_path,
        check=True,
    )

    _print_next_steps(project_path)
