"""``abi deploy dokploy``: a Docker Compose stack for a Dokploy server.

Dokploy's Traefik is the edge, so the stack routes through Traefik labels on
the external ``dokploy-network`` instead of the local Caddy service, publishes
no host port, and builds ``abi`` from the project Dockerfile on each deploy.
Its values live in Dokploy's Environment tab; this command writes a starting
set to the gitignored ``.env.dokploy``. See docs/deploy-dokploy.md.
"""

import os
import re
import secrets
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import jinja2
import yaml
from rich.prompt import Prompt

import naas_abi_cli

from ..admin_credentials import (
    ADMIN_EMAIL,
    ADMIN_EMAIL_KEY,
    ADMIN_PASSWORD_KEY,
    NATS_PASSWORDS,
    ensure_admin_credentials,
    ensure_nats_passwords,
    ensure_nats_secret,
    generate_admin_password,
    generate_nats_password,
)
from .local import (
    DEFAULT_ENV_VALUES,
    _build_hosts_from_domain,
    _build_nexus_api_url,
    _read_env_vars,
    compose_project_name,
    project_uses_nats,
)

COMPOSE_FILE = "docker-compose.dokploy.yml"
CONFIG_FILE = "config.dokploy.yaml"
ENV_FILE = ".env.dokploy"
BACKUP_DIRECTORY = os.path.join(".abi-backups", "deploy-dokploy")
# The writable dotenv secret file, on the abi_secrets volume: secrets the
# engine stores at runtime (generated user passwords, keys saved from Nexus)
# outlive a redeploy. Replaces the project's `.env` dotenv adapter.
SECRETS_DIR = "/var/lib/abi-secrets"
SECRETS_FILE = f"{SECRETS_DIR}/.env"
# Where coding-init writes the minted admin tokens: on the coding_secrets
# volume, which abi mounts read-only and reads as a read-only dotenv adapter.
CODING_SECRETS_DIR = "/run/abi-secrets"
CODING_SECRETS_FILE = f"{CODING_SECRETS_DIR}/coding.env"
# Minted at deploy time into CODING_SECRETS_FILE. Never written to the env: an
# environment variable, even empty, wins over the dotenv file.
_MINTED_TOKENS = frozenset({"CODER_ADMIN_TOKEN", "FORGEJO_ADMIN_TOKEN"})
# The Traefik resolver for the *.coder wildcard certificate; set only with a
# DNS-challenge resolver.
_WILDCARD_RESOLVER_KEY = "CODER_WILDCARD_CERT_RESOLVER"

# .deploy/docker files the compose mounts, rendered from the local and coding
# templates `abi deploy local` uses.
_LOCAL_FILES = (
    "docker/postgres/initdb/001-create-dagster-db.sql",
    "docker/postgres/initdb/002-create-nexus-db.sql",
    "docker/postgres/initdb/005-create-ducklake-db.sql",
    "docker/nats/nats.conf",
    "docker/dagster/dagster.yaml",
)
_CODING_FILES = (
    "docker/postgres/initdb/003-create-coder-db.sql",
    "docker/postgres/initdb/004-create-forgejo-db.sql",
    "docker/bootstrap-coding.sh",
)

_SECRET_REF = re.compile(r"\{\{\s*secret\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
_JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")
_SECRET_ADAPTERS_KEY = re.compile(r"(?P<indent>[ \t]*)secret_adapters:[ \t]*(#.*)?")


class DokployDeployError(Exception):
    """The project cannot be rendered for Dokploy."""


def _templates(name: str) -> str:
    return os.path.join(
        os.path.dirname(naas_abi_cli.__file__), "cli/deploy/templates", name
    )


def _stack_name(project_path: str) -> str:
    # Also a DNS alias prefix: no underscores in host names.
    return compose_project_name(project_path).replace("_", "-").strip("-") or "abi"


def _render_compose(nats: bool, include_coding: bool, wildcard_cert: bool) -> str:
    with open(
        os.path.join(_templates("dokploy"), COMPOSE_FILE), "r", encoding="utf-8"
    ) as template:
        source = template.read()
    return jinja2.Template(
        source,
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
    ).render(
        NATS=nats,
        INCLUDE_CODING=include_coding,
        CODER_WILDCARD_CERT=wildcard_cert,
        SECRETS_DIR=SECRETS_DIR,
        CODING_SECRETS_DIR=CODING_SECRETS_DIR,
        CODING_SECRETS_FILE=CODING_SECRETS_FILE,
    )


def _render_deploy_files(
    include_coding: bool, values: dict[str, object]
) -> dict[str, str]:
    """The .deploy/docker files the compose mounts: {relative path: content}.

    Rendered from the same templates as `abi deploy local`, so a project that
    runs both stacks gets the same files.
    """
    wanted = [("local", path) for path in _LOCAL_FILES]
    if include_coding:
        wanted += [("coding", path) for path in _CODING_FILES]

    files: dict[str, str] = {}
    for tree, path in wanted:
        with open(os.path.join(_templates(tree), path), "r", encoding="utf-8") as src:
            files[os.path.join(".deploy", path)] = jinja2.Template(
                src.read(),
                undefined=jinja2.StrictUndefined,
                keep_trailing_newline=True,
            ).render(values)
    return files


def _without_jinja(text: str) -> str:
    return _JINJA.sub("x", text)


def _persistent_dotenv(adapter: Any) -> Any:
    """The adapter, with a dotenv on the project's `.env` moved to SECRETS_FILE.

    `.env` is in the image, so what the engine writes there is lost on the next
    deploy. Other paths are the project's choice and are kept.
    """
    if not isinstance(adapter, dict):
        return adapter
    config = adapter.get("config")
    if adapter.get("adapter") == "dotenv":
        config = dict(config or {})
        if os.path.normpath(str(config.get("path", ".env"))) == ".env":
            config["path"] = SECRETS_FILE
        return {**adapter, "config": config}
    if adapter.get("adapter") == "base64" and isinstance(config, dict):
        inner = _persistent_dotenv(config.get("secret_adapter"))
        return {**adapter, "config": {**config, "secret_adapter": inner}}
    return adapter


class _IndentedDumper(yaml.SafeDumper):
    """Indents list items under their key, as config.local.yaml does."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)


def _secret_adapters_block(local_config: str) -> tuple[int, int, str]:
    """(first line, line after, indent) of the secret_adapters block."""
    lines = local_config.splitlines()
    for start, line in enumerate(lines):
        match = _SECRET_ADAPTERS_KEY.fullmatch(line)
        if match:
            indent = match.group("indent")
            break
    else:
        raise DokployDeployError(
            "config.local.yaml has no services.secret.secret_adapters list. "
            "Add one (see the `abi new project` template) and rerun."
        )

    end = start + 1
    last = start
    while end < len(lines):
        line = lines[end]
        if not line.strip():
            end += 1
            continue
        rest = line[len(indent) :] if line.startswith(indent) else ""
        if rest.startswith((" ", "\t", "-")):
            last = end
            end += 1
            continue
        break
    return start, last + 1, indent


def _dokploy_config(local_config: str, include_coding: bool) -> str:
    """config.dokploy.yaml: config.local.yaml with its secret adapters set for
    Dokploy.

    The project's adapters are kept, with the `.env` dotenv moved onto the
    abi_secrets volume; with coding, the minted tokens are appended as a
    read-only dotenv. Only the secret_adapters block is rewritten, so the rest
    of the file keeps its comments.
    """
    header = (
        "# Generated by `abi deploy dokploy` from config.local.yaml; rerunning\n"
        "# the command rewrites it. Edit config.local.yaml instead. The Dokploy\n"
        "# stack sets ENV=dokploy, so the engine reads this file.\n"
    )
    if not local_config.endswith("\n"):
        local_config += "\n"
    start, end, indent = _secret_adapters_block(local_config)
    lines = local_config.splitlines(keepends=True)

    try:
        # The key at column 0; its items stay deeper, so the YAML holds.
        parsed = yaml.safe_load(
            "".join([lines[start].lstrip()] + lines[start + 1 : end])
        )
    except yaml.YAMLError as error:
        raise DokployDeployError(
            f"Cannot read services.secret.secret_adapters in config.local.yaml: {error}"
        ) from error
    adapters = parsed.get("secret_adapters") if isinstance(parsed, dict) else None
    if not isinstance(adapters, list):
        raise DokployDeployError(
            "services.secret.secret_adapters in config.local.yaml is not a list."
        )

    adapters = [_persistent_dotenv(adapter) for adapter in adapters]
    if include_coding:
        adapters.append(
            {
                "adapter": "dotenv",
                "config": {"path": CODING_SECRETS_FILE, "read_only": True},
            }
        )
    dumped = yaml.dump(
        {"secret_adapters": adapters},
        Dumper=_IndentedDumper,
        sort_keys=False,
        default_flow_style=False,
        width=1000,
    )
    comment = [
        "# Set by `abi deploy dokploy`: the `.env` dotenv is on the abi_secrets\n",
    ]
    if include_coding:
        comment.append(
            "# volume; the coding tokens are read from the coding_secrets volume.\n"
        )
    else:
        comment.append("# volume.\n")
    block = [indent + line for line in comment]
    block += [f"{indent}{line}\n" for line in dumped.splitlines()]
    config = "".join(lines[:start] + block + lines[end:])

    # The engine must see exactly these adapters: no leftover of the old block.
    try:
        rendered = yaml.safe_load(_without_jinja(config))
        seen = rendered["services"]["secret"]["secret_adapters"]
    except (yaml.YAMLError, KeyError, TypeError) as error:
        raise DokployDeployError(
            "Cannot rewrite services.secret.secret_adapters in config.local.yaml "
            f"({error}). Keep it a plain YAML list under services.secret."
        ) from error
    if seen != yaml.safe_load(_without_jinja(dumped))["secret_adapters"]:
        raise DokployDeployError(
            "Cannot rewrite services.secret.secret_adapters in config.local.yaml: "
            "the rewritten list does not read back as written. Keep it a plain "
            "YAML list under services.secret."
        )
    return header + config


def _config_secret_names(config: str) -> list[str]:
    """The ``secret.X`` names the config reads, outside YAML comments."""
    names: list[str] = []
    for line in config.splitlines():
        if line.lstrip().startswith("#"):
            continue
        for name in _SECRET_REF.findall(line):
            if name not in names:
                names.append(name)
    return names


def _with_ignored(path: Path, entries: list[str]) -> str | None:
    """The ignore file with ``entries`` added, or None if it has them all."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    missing = [entry for entry in entries if entry not in lines]
    if not missing:
        return None
    if lines and lines[-1].strip():
        lines.append("")
    lines += ["# abi deploy dokploy", *missing]
    return "\n".join(lines) + "\n"


def _env_layout(
    *,
    stack_name: str,
    hosts: dict[str, str],
    nats: bool,
    include_coding: bool,
    wildcard_resolver: str | None,
    config_secrets: list[str],
) -> list[tuple[str, list[tuple[str, Callable[[], str]]]]]:
    """Sections of .env.dokploy: (title, [(key, value factory)])."""

    def fixed(value: str) -> Callable[[], str]:
        return lambda: value

    def uuid() -> str:
        return str(uuid4())

    def password() -> str:
        # Complexity-safe (upper+lower+digit+special) for Coder and Forgejo.
        return f"Abi1!{secrets.token_urlsafe(24)}"

    stack: list[tuple[str, Callable[[], str]]] = [
        # Router names, DNS aliases and the network name; unique per stack on a
        # server.
        ("ABI_STACK_NAME", fixed(stack_name)),
        ("PUBLIC_WEB_HOST", fixed(hosts["PUBLIC_WEB_HOST"])),
        ("PUBLIC_API_HOST", fixed(hosts["PUBLIC_API_HOST"])),
        ("NEXUS_API_URL", fixed(hosts["NEXUS_API_URL"])),
        ("TRAEFIK_CERT_RESOLVER", fixed("letsencrypt")),
        ("NEXUS_WEB_IMAGE", fixed(DEFAULT_ENV_VALUES["NEXUS_WEB_IMAGE"])),
        ("NEXUS_WEB_TAG", fixed(DEFAULT_ENV_VALUES["NEXUS_WEB_TAG"])),
    ]
    admin: list[tuple[str, Callable[[], str]]] = [
        (ADMIN_EMAIL_KEY, fixed(ADMIN_EMAIL)),
        (ADMIN_PASSWORD_KEY, generate_admin_password),
    ]
    infrastructure: list[tuple[str, Callable[[], str]]] = [
        ("ABI_API_KEY", uuid),
        ("POSTGRES_USER", fixed(DEFAULT_ENV_VALUES["POSTGRES_USER"])),
        ("POSTGRES_PASSWORD", uuid),
        ("POSTGRES_DB", fixed(DEFAULT_ENV_VALUES["POSTGRES_DB"])),
        ("POSTGRES_PORT", fixed(DEFAULT_ENV_VALUES["POSTGRES_PORT"])),
        ("QDRANT_PORT", fixed(DEFAULT_ENV_VALUES["QDRANT_PORT"])),
        ("REDIS_PORT", fixed(DEFAULT_ENV_VALUES["REDIS_PORT"])),
        ("MINIO_PORT", fixed(DEFAULT_ENV_VALUES["MINIO_PORT"])),
        ("MINIO_ROOT_USER", fixed(DEFAULT_ENV_VALUES["MINIO_ROOT_USER"])),
        ("MINIO_ROOT_PASSWORD", uuid),
        ("FUSEKI_ADMIN_PASSWORD", uuid),
        (
            "FUSEKI_COMPACT_INTERVAL_SECONDS",
            fixed(DEFAULT_ENV_VALUES["FUSEKI_COMPACT_INTERVAL_SECONDS"]),
        ),
    ]
    if nats:
        infrastructure += [(key, generate_nats_password) for key in NATS_PASSWORDS]
        infrastructure.append(("NATS_JWT_SECRET", lambda: secrets.token_urlsafe(48)))
    else:
        infrastructure += [
            ("RABBITMQ_USER", fixed(DEFAULT_ENV_VALUES["RABBITMQ_USER"])),
            ("RABBITMQ_PASSWORD", uuid),
        ]

    sections = [
        ("Stack: hosts and routing", stack),
        ("Nexus admin login (generated for this stack)", admin),
        ("Infrastructure (generated)", infrastructure),
    ]
    if include_coding:
        coding: list[tuple[str, Callable[[], str]]] = []
        if wildcard_resolver:
            # The DNS-challenge resolver for *.coder.<web host>; changing
            # whether it is set needs a rerun (the compose labels follow it).
            coding.append((_WILDCARD_RESOLVER_KEY, fixed(wildcard_resolver)))
        coding += [
            ("CODING_FORGEJO_ORG", fixed("abi")),
            ("CODER_ADMIN_EMAIL", fixed(ADMIN_EMAIL)),
            ("CODER_ADMIN_USERNAME", fixed("admin")),
            ("CODER_ADMIN_PASSWORD", password),
            ("FORGEJO_ADMIN_EMAIL", fixed(ADMIN_EMAIL)),
            ("FORGEJO_ADMIN_USERNAME", fixed("forgejo-admin")),
            ("FORGEJO_ADMIN_PASSWORD", password),
            # Forgejo runner registration: a 40-char hex shared secret.
            ("FORGEJO_RUNNER_REGISTRATION_TOKEN", lambda: secrets.token_hex(20)),
        ]
        sections.append(
            (
                (
                    "Coding workspaces (Coder + Forgejo + Actions CI). The admin "
                    "tokens are minted on the coding_secrets volume, not here."
                ),
                coding,
            )
        )

    listed = {key for _, entries in sections for key, _ in entries}
    from_config = [
        (name, fixed(""))
        for name in config_secrets
        if name not in listed and name not in _MINTED_TOKENS
    ]
    if from_config:
        sections.append(
            ("Read by config.dokploy.yaml: fill in the empty ones", from_config)
        )
    return sections


def _render_env(
    sections: list[tuple[str, list[tuple[str, Callable[[], str]]]]],
    existing: dict[str, str],
    overrides: dict[str, str],
) -> tuple[str, list[str]]:
    """The content of .env.dokploy, and the keys left empty."""
    lines = [
        "# Paste into the Dokploy compose app's Environment tab.",
        (
            "# Generated by `abi deploy dokploy`; values are kept on reruns, "
            "`--regenerate` replaces them."
        ),
        "# Gitignored: it holds this stack's passwords.",
    ]
    written: set[str] = set()
    empty: list[str] = []
    for title, entries in sections:
        lines += ["", f"# {title}"]
        for key, factory in entries:
            if key in overrides:
                value = overrides[key]
            elif key in existing:
                value = existing[key]
            else:
                value = factory()
            lines.append(f"{key}={value}")
            written.add(key)
            if value == "":
                empty.append(key)

    custom = [
        key
        for key in existing
        if key not in written
        and key not in _MINTED_TOKENS
        and key != _WILDCARD_RESOLVER_KEY
    ]
    if custom:
        lines += ["", "# Your own values"]
        lines += [f"{key}={existing[key]}" for key in custom]

    return "\n".join(lines) + "\n", empty


def _backup_env(project_path: str, env_path: Path) -> str | None:
    if not env_path.exists():
        return None
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(project_path, BACKUP_DIRECTORY, timestamp)
    os.makedirs(backup_path, exist_ok=True)
    shutil.copy2(env_path, os.path.join(backup_path, ENV_FILE))
    return backup_path


def _print_next_steps(
    hosts: dict[str, str],
    include_coding: bool,
    wildcard_cert: bool,
    empty: list[str],
) -> None:
    web, api = hosts["PUBLIC_WEB_HOST"], hosts["PUBLIC_API_HOST"]
    print(f"\nWrote {COMPOSE_FILE}, {CONFIG_FILE}, .deploy/docker and {ENV_FILE}.")
    print("\nNext steps")
    print(
        f"1. Commit {COMPOSE_FILE}, {CONFIG_FILE} and .deploy/ "
        f"(never {ENV_FILE}) and push."
    )
    print(
        "2. In Dokploy, create a Compose app from this repository, compose type "
        f"Docker Compose, compose path ./{COMPOSE_FILE}."
    )
    print(f"3. Paste {ENV_FILE} into the app's Environment tab.")
    if empty:
        print(f"   Fill in first: {', '.join(empty)}")
    records = [web, api]
    if include_coding:
        records += [f"coder.{web}", f"*.coder.{web}", f"git.{web}"]
    print(f"4. Point these DNS records at the Dokploy server: {', '.join(records)}")
    if include_coding and not wildcard_cert:
        print(
            "   Workspace apps on *.coder get Traefik's default certificate until "
            "you add a DNS-challenge resolver to Dokploy's Traefik and rerun with "
            "--wildcard-cert-resolver <name>."
        )
    print(
        f"5. Deploy, then sign in at https://{web} with the admin login in {ENV_FILE}."
    )
    print("Guide: docs/deploy-dokploy.md in the ABI repository.\n")


def setup_dokploy_deploy(
    project_path: str,
    domain: str | None = None,
    include_coding: bool = False,
    regenerate: bool = False,
    nats: bool | None = None,
    wildcard_cert_resolver: str | None = None,
) -> None:
    """Render the Dokploy stack and its env into ``project_path``.

    ``docker-compose.dokploy.yml``, ``config.dokploy.yaml`` and the
    ``.deploy/docker`` files are rewritten on every run. ``.env.dokploy`` keeps
    its values unless ``regenerate``; ``domain`` moves the hosts only.
    ``wildcard_cert_resolver`` names a DNS-challenge resolver for the
    ``*.coder`` certificate; it is kept on later runs, even regenerated ones.
    """
    project_path = os.path.abspath(os.path.expanduser(project_path))
    local_config_path = os.path.join(project_path, "config.local.yaml")
    if not os.path.exists(local_config_path):
        raise DokployDeployError(
            f"No config.local.yaml in {project_path}: run `abi deploy dokploy` "
            "from an ABI project (created with `abi new project`)."
        )
    if wildcard_cert_resolver is not None and not include_coding:
        raise DokployDeployError(
            "--wildcard-cert-resolver only applies to the coding stack: add --coding."
        )
    if nats is None:
        nats = bool(project_uses_nats(project_path))
    if not os.path.exists(os.path.join(project_path, "Dockerfile")):
        print(
            "Warning: no Dockerfile at the project root. Dokploy builds `abi` "
            "from it: add one (see the `abi new project` template)."
        )

    env_path = Path(project_path) / ENV_FILE
    existing = _read_env_vars(str(env_path))
    if wildcard_cert_resolver is None:
        wildcard_cert_resolver = existing.get(_WILDCARD_RESOLVER_KEY) or None
    wildcard_cert = include_coding and bool(wildcard_cert_resolver)
    if regenerate:
        existing = {}

    overrides: dict[str, str] = {}
    if domain is None and "PUBLIC_WEB_HOST" not in existing:
        domain = Prompt.ask("Domain (example: example.com)")
    if domain is not None:
        hosts = _build_hosts_from_domain(domain)
        overrides = {
            "PUBLIC_WEB_HOST": hosts["PUBLIC_WEB_HOST"],
            "PUBLIC_API_HOST": hosts["PUBLIC_API_HOST"],
            "NEXUS_API_URL": _build_nexus_api_url(
                public_api_host=hosts["PUBLIC_API_HOST"], public_api_scheme="https"
            ),
        }
    hosts = {
        key: overrides.get(key) or existing.get(key, "")
        for key in ("PUBLIC_WEB_HOST", "PUBLIC_API_HOST", "NEXUS_API_URL")
    }
    if wildcard_cert and wildcard_cert_resolver:
        overrides[_WILDCARD_RESOLVER_KEY] = wildcard_cert_resolver

    # Render everything before writing anything: a failure leaves the
    # project's files as they were.
    with open(local_config_path, "r", encoding="utf-8") as config_file:
        dokploy_config = _dokploy_config(config_file.read(), include_coding)
    files = {
        COMPOSE_FILE: _render_compose(
            nats=nats, include_coding=include_coding, wildcard_cert=wildcard_cert
        ),
        CONFIG_FILE: dokploy_config,
        **_render_deploy_files(
            include_coding=include_coding,
            values={
                **DEFAULT_ENV_VALUES,
                "NATS": nats,
                "INCLUDE_CODING": include_coding,
                "INCLUDE_HEADSCALE": False,
            },
        ),
    }
    sections = _env_layout(
        stack_name=_stack_name(project_path),
        hosts=hosts,
        nats=nats,
        include_coding=include_coding,
        wildcard_resolver=wildcard_cert_resolver if wildcard_cert else None,
        config_secrets=_config_secret_names(dokploy_config),
    )
    files[ENV_FILE], empty = _render_env(sections, existing, overrides)
    # Dokploy writes the Environment tab to .env in the build context: keep it
    # out of the image.
    for name, entries in (
        (".gitignore", [ENV_FILE]),
        (".dockerignore", [".env", ".env.*"]),
    ):
        content = _with_ignored(Path(project_path) / name, entries)
        if content is not None:
            files[name] = content

    if regenerate:
        backup_path = _backup_env(project_path, env_path)
        if backup_path is not None:
            print(f"Backed up the previous {ENV_FILE} to {backup_path}")
    for name, content in files.items():
        target = os.path.join(project_path, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as out:
            out.write(content)

    # Validators: they keep valid values and replace a shipped default or a
    # value too short to be safe.
    ensure_admin_credentials(env_path)
    if nats:
        ensure_nats_passwords(env_path)
        ensure_nats_secret(env_path)

    _print_next_steps(
        hosts, include_coding=include_coding, wildcard_cert=wildcard_cert, empty=empty
    )
