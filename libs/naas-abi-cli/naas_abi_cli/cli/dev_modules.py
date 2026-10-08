"""SDK modules `abi dev up --with-nats` runs next to the engine.

Declared under `dev.modules` in the project config (EngineConfiguration_Dev).
Each runs as `python -m <module> <args>` under `dev_supervisor`, which restarts
it when it exits on its own. Its environment carries the dev broker from the
overlay `abi dev up --with-nats` generates:

- ``ABI_NATS_URL``, logged in as the broker user ``module``,
  ``NATS_JWT_SECRET`` and ``ABI_DISCOVERY_PROJECT``;
- ``ABI_SERVICE_TOKEN``, a service token for the module's name, as
  ``python -m naas_abi_sdk.module_runner`` expects;
- ``OTEL_EXPORTER_OTLP_ENDPOINT`` with ``--with-tracing``;
- the project's ``src/`` first on ``PYTHONPATH``.

The module's own ``env`` comes last; its values may name the above as ``${VAR}``.
"""

from __future__ import annotations

import json
import os
import string
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

# A dev process's token. Modules holding NATS_JWT_SECRET can issue their own.
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


def read_overlay(path: Path) -> dict:
    """The generated dev overlay: JSON after a comment line."""
    body = "\n".join(
        line for line in path.read_text().splitlines() if not line.startswith("#")
    )
    return json.loads(body)


def module_environment(
    module: DevModuleConfiguration,
    overlay: dict,
    project_root: Path,
    base: Mapping[str, str],
    *,
    nats_password: str,
) -> dict[str, str]:
    """``nats_password``: the broker user ``module``'s (NATS_MODULE_PASSWORD)."""
    from naas_abi_core.engine.nats_auth import issue_service_token

    nats = overlay["nats"]
    env = dict(base)
    env.update(
        ABI_NATS_URL=nats_login(nats["nats_url"], "module", nats_password),
        NATS_JWT_SECRET=nats["jwt_secret"],
        ABI_DISCOVERY_PROJECT=nats["discovery"]["project"],
        ABI_SERVICE_TOKEN=issue_service_token(
            module.name, nats["jwt_secret"], ttl=SERVICE_TOKEN_TTL
        ),
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
