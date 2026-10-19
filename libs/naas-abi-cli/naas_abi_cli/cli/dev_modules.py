"""SDK modules `abi dev up` runs next to the engine in NATS mode (the default).

Declared under `dev.modules` in the project config (EngineConfiguration_Dev).
Each runs as `python -m <module> <args>` under `dev_supervisor`, which restarts
it when it exits on its own. Its environment carries the dev broker from the
overlay `abi dev up` generates:

- ``ABI_NATS_URL``, the broker with no login: the module brings its key;
- ``ABI_SERVICE_KEY``, a fresh key of its service account
  (``module/<project>/<module_id>``), as ``python -m naas_abi_sdk.module_runner``
  expects, and ``ABI_DISCOVERY_PROJECT``;
- ``OTEL_EXPORTER_OTLP_ENDPOINT`` with ``--with-tracing``;
- the project's ``src/`` first on ``PYTHONPATH``.

No signing secret, broker password or other key reaches it: the CLI's own
``NATS_*`` variables and ``iam/`` secrets are left out. The module's own
``env`` comes last; its values may name the above as ``${VAR}``.
"""

from __future__ import annotations

import json
import os
import string
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

if TYPE_CHECKING:
    from naas_abi_core.engine.engine_configuration.EngineConfiguration_Dev import (
        DevModuleConfiguration,
    )

# Never passed on to a module: broker logins, the callout seed, IAM's secrets.
_WITHHELD_PREFIXES = ("NATS_", "iam/", "ABI_SERVICE_KEY")

# The built-in identity provider (libs/naas-abi-idp), the default provider of
# `abi dev up`. It runs as the module account module/<project>/idp.
IDP_MODULE = "naas_abi_idp"
IDP_NAME = "idp"
IDP_CLIENT_ID = "abi"
IDP_ISSUER_ENV = "ABI_IDP_ISSUER"
IDP_PROVIDER = "builtin"


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


def configured_identity(config_file: str | Path) -> dict | None:
    """The top-level ``identity:`` block of a project config, rendered without
    secrets and not validated; None when the config has none."""
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )

    path = Path(config_file)
    data = EngineConfiguration.render_without_secrets(
        path.read_text(encoding="utf-8"), base_dir=str(path.resolve().parent)
    )
    identity = data.get("identity") if isinstance(data, dict) else None
    return identity if isinstance(identity, dict) else None


def has_identity_providers(identity: dict | None) -> bool:
    return bool((identity or {}).get("providers"))


def wants_builtin_idp(identity: dict | None) -> bool:
    """Whether ``abi dev up`` runs the built-in IdP: the project names it
    (``provisioning: builtin``), or names no provider at all, in which case the
    dev overlay configures it. A project with providers of its own gets none."""
    providers = (identity or {}).get("providers") or []
    if not providers:
        return True
    return any(
        isinstance(p, dict) and p.get("provisioning") == "builtin" for p in providers
    )


def is_builtin_idp(module: DevModuleConfiguration) -> bool:
    return module.module == IDP_MODULE


def implicit_idp_module() -> DevModuleConfiguration:
    from naas_abi_core.engine.engine_configuration.EngineConfiguration_Dev import (
        DevModuleConfiguration,
    )

    return DevModuleConfiguration(name=IDP_NAME, module=IDP_MODULE, module_id=IDP_NAME)


def with_builtin_idp(
    modules: dict[str, DevModuleConfiguration], identity: dict | None
) -> dict[str, DevModuleConfiguration]:
    """``modules``, plus the built-in IdP when ``abi dev up`` should run it and
    the project does not declare it as a dev module itself."""
    if not wants_builtin_idp(identity) or any(
        is_builtin_idp(m) for m in modules.values()
    ):
        return modules
    return {**modules, IDP_NAME: implicit_idp_module()}


def builtin_identity(issuer: str, client_secret: str) -> dict:
    """The ``identity`` block the dev overlay adds when the project has none."""
    return {
        "default_provider": IDP_PROVIDER,
        "providers": [
            {
                "name": IDP_PROVIDER,
                "display_name": "Email code",
                "issuer": issuer,
                "client_id": IDP_CLIENT_ID,
                "client_secret": client_secret,
                "groups_claim": "groups",
                "scopes": ["openid", "email", "profile", "groups", "offline_access"],
                "provisioning": "builtin",
            }
        ],
    }


def idp_environment(api_origin: str, client_secret: str) -> dict[str, str]:
    """What the built-in IdP module is told: where it is served, the client ABI
    signs in as, and (dev only, the mail goes to a local file) that an address
    may register itself. ``api_origin``: where the browser reaches the API."""
    return {
        IDP_ISSUER_ENV: f"{api_origin}/idp",
        "ABI_IDP_CLIENT_ID": IDP_CLIENT_ID,
        "ABI_IDP_CLIENT_SECRET": client_secret,
        "ABI_IDP_REDIRECT_URIS": f"{api_origin}/api/auth/oidc/callback",
        "ABI_IDP_SIGNUP": "1",
    }


def read_overlay(path: Path) -> dict:
    """The generated dev overlay: JSON after a comment line."""
    body = "\n".join(
        line for line in path.read_text().splitlines() if not line.startswith("#")
    )
    return json.loads(body)


def without_login(url: str) -> str:
    """``url`` with its ``user:password@`` removed."""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(netloc=parts.netloc.rpartition("@")[2]))


def module_environment(
    module: DevModuleConfiguration,
    overlay: dict,
    project_root: Path,
    base: Mapping[str, str],
    *,
    service_key: str,
) -> dict[str, str]:
    """``service_key``: the module's own (``abi dev up`` creates it)."""
    nats = overlay["nats"]
    env = {
        key: value
        for key, value in base.items()
        if not key.startswith(_WITHHELD_PREFIXES)
    }
    env.update(
        ABI_NATS_URL=without_login(nats["nats_url"]),
        ABI_SERVICE_KEY=service_key,
        ABI_DISCOVERY_PROJECT=nats["discovery"]["project"],
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
