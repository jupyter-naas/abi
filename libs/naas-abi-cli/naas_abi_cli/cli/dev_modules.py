"""SDK modules `abi dev up` runs next to the engine in NATS mode (the default).

Declared under `dev.modules` in the project config (EngineConfiguration_Dev).
Each runs as `python -m <module> <args>` under `dev_supervisor`, which restarts
it when it exits on its own. Its environment carries the dev broker from the
overlay `abi dev up` generates:

- ``ABI_NATS_URL``, logged in as the broker user ``module``, and
  ``ABI_DISCOVERY_PROJECT``;
- ``ABI_MODULE_KEY``, the module key of its module id (its ``identity``, else
  the ``module_id`` of the ``ABIModule`` its package exports), and
  ``ABI_SERVICE_TOKEN``, a token signed with it, for modules that read only
  that. Never the project secret: a module can sign for its own id only, and
  discovery registers it only under that id;
- ``OTEL_EXPORTER_OTLP_ENDPOINT`` with ``--with-tracing``;
- the project's ``src/`` first on ``PYTHONPATH``.

The module's own ``env`` comes last; its values may name the above as ``${VAR}``.
"""

from __future__ import annotations

import json
import os
import string
import subprocess
import sys
from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from naas_abi_cli.cli.admin_credentials import nats_login

if TYPE_CHECKING:
    from naas_abi_core.engine.engine_configuration.EngineConfiguration_Dev import (
        DevModuleConfiguration,
    )

# A dev process's token. Modules sign fresh ones with their ABI_MODULE_KEY.
SERVICE_TOKEN_TTL = timedelta(days=7)


def load_dev_modules() -> dict[str, DevModuleConfiguration]:
    """The enabled `dev.modules`, by name, from the config the engine loads;
    none without a config file. Raises ValueError for an invalid block."""
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )
    from naas_abi_core.engine.engine_configuration.EngineConfiguration_Dev import (
        load_dev_configuration,
    )

    try:
        config_file = EngineConfiguration.configuration_file()
    except FileNotFoundError:
        return {}
    modules = load_dev_configuration(config_file).enabled_modules()
    return {module.name: module for module in modules}


def configured_nats(config_file: str | Path) -> dict | None:
    """The top-level ``nats:`` block of a project config, rendered without
    secrets (their values are empty); None when the config has none."""
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )

    path = Path(config_file)
    data = EngineConfiguration.render_without_secrets(
        path.read_text(encoding="utf-8"), base_dir=str(path.resolve().parent)
    )
    nats = data.get("nats") if isinstance(data, dict) else None
    return nats if isinstance(nats, dict) else None


def configured_discovery_project(config_file: str | Path) -> str | None:
    """``nats.discovery.project`` of a project config, if it declares one."""
    discovery = (configured_nats(config_file) or {}).get("discovery")
    project = discovery.get("project") if isinstance(discovery, dict) else None
    return project if isinstance(project, str) and project else None


def read_overlay(path: Path) -> dict:
    """The generated dev overlay: JSON after a comment line."""
    body = "\n".join(
        line for line in path.read_text().splitlines() if not line.startswith("#")
    )
    return json.loads(body)


# Prints the module id of the ABIModule a package exports, as naas-abi-module
# reads it (module_id, else the class's module), or nothing without one.
_MODULE_ID = (
    "import importlib, sys\n"
    "t = getattr(importlib.import_module(sys.argv[1]), 'ABIModule', None)\n"
    "print((getattr(t, 'module_id', None) or t.__module__) if t is not None else '')\n"
)


def module_identity(
    module: DevModuleConfiguration, project_root: Path, base: Mapping[str, str]
) -> str:
    """The module id ``module`` registers as: its ``identity``, else read from the
    ``ABIModule`` its package exports (in a subprocess: the CLI never imports the
    project's code). Raises ValueError when neither tells it."""
    if module.identity:
        return module.identity
    env = dict(base)
    src = project_root / "src"
    if src.is_dir():
        env["PYTHONPATH"] = os.pathsep.join(
            [str(src), *filter(None, [base.get("PYTHONPATH", "")])]
        )
    try:
        result = subprocess.run(
            [sys.executable, "-c", _MODULE_ID, module.module],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        lines = result.stdout.strip().splitlines() if result.returncode == 0 else []
    except (OSError, subprocess.SubprocessError):
        lines = []
    if not lines or not lines[-1].strip():
        raise ValueError(
            f"dev module {module.name!r}: cannot tell the module id it registers as "
            f"({module.module} exports no ABIModule); add `identity: <module_id>` "
            "to its dev.modules entry"
        )
    return lines[-1].strip()


def module_environment(
    module: DevModuleConfiguration,
    overlay: dict,
    project_root: Path,
    base: Mapping[str, str],
    *,
    nats_password: str,
) -> dict[str, str]:
    """``nats_password``: the broker user ``module``'s (NATS_MODULE_PASSWORD)."""
    from naas_abi_core.engine.nats_auth import issue_module_token, module_key

    nats = overlay["nats"]
    identity = module_identity(module, project_root, base)
    key = module_key(nats["jwt_secret"], identity)
    env = dict(base)
    env.pop("NATS_JWT_SECRET", None)  # the engine's, never a module's
    env.update(
        ABI_NATS_URL=nats_login(nats["nats_url"], "module", nats_password),
        ABI_DISCOVERY_PROJECT=nats["discovery"]["project"],
        ABI_MODULE_KEY=key,
        ABI_SERVICE_TOKEN=issue_module_token(identity, key, ttl=SERVICE_TOKEN_TTL),
    )
    src = project_root / "src"
    if src.is_dir():
        env["PYTHONPATH"] = os.pathsep.join(
            [str(src), *filter(None, [base.get("PYTHONPATH", "")])]
        )
    telemetry = overlay.get("telemetry") or {}
    if telemetry.get("enabled") and telemetry.get("otlp_endpoint"):
        env["OTEL_EXPORTER_OTLP_ENDPOINT"] = telemetry["otlp_endpoint"]
    for key, value in module.env.items():
        env[key] = string.Template(value).safe_substitute(env)
    return env


def module_command(module: DevModuleConfiguration) -> list[str]:
    return [
        sys.executable,
        "-m",
        "naas_abi_cli.cli.dev_supervisor",
        "--restart",
        module.restart,
        "--",
        sys.executable,
        "-m",
        module.module,
        *module.args,
    ]
