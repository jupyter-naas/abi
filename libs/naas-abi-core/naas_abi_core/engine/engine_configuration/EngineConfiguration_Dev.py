"""The ``dev:`` block: SDK modules ``abi dev up --with-nats`` runs next to the engine.

The engine validates the block (so a typo fails at load) and otherwise ignores
it: it is for the dev CLI, which spawns each enabled module as
``python -m <module> <args>`` with the dev broker's settings in its environment
(``ABI_NATS_URL``, ``NATS_JWT_SECRET``, ``ABI_SERVICE_TOKEN``,
``ABI_DISCOVERY_PROJECT``, and ``OTEL_EXPORTER_OTLP_ENDPOINT`` with tracing).
``env`` values may name those as ``${VAR}``.

    dev:
      modules:
        - name: probe-researcher            # process name: logs, pid, --service
          module: operations.projects.nats_probe
          args: [researcher]
          env: {NATS_PROBE_DISCOVERY_PROJECT: "${ABI_DISCOVERY_PROJECT}"}
          restart: on-failure               # or always, never
"""

from __future__ import annotations

import os
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DevModuleConfiguration(BaseModel):
    """One SDK module (remote, NATS-only) run by ``abi dev up --with-nats``."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")
    module: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    restart: Literal["on-failure", "always", "never"] = "on-failure"


class DevConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modules: list[DevModuleConfiguration] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_names(self) -> Self:
        names = [module.name for module in self.modules]
        if len(names) != len(set(names)):
            raise ValueError("dev.modules names must be unique")
        return self

    def enabled_modules(self) -> list[DevModuleConfiguration]:
        return [module for module in self.modules if module.enabled]


def load_dev_configuration(config_file: str | None = None) -> DevConfiguration:
    """The ``dev:`` block of the config the engine loads (``config.{ENV}.yaml`` or
    ``config.yaml``), rendered without secrets: the CLI has no secret service."""
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )

    path = config_file or EngineConfiguration.configuration_file()
    with open(path) as file:
        content = file.read()
    data = EngineConfiguration.render_without_secrets(
        content, base_dir=os.path.dirname(os.path.abspath(path))
    )
    dev = data.get("dev") if isinstance(data, dict) else None
    return DevConfiguration.model_validate(dev or {})
