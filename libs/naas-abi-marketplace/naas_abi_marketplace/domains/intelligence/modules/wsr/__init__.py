"""World Situation Room — a loadable module of the ``intelligence`` bucket.

* **Configuration** — the data-source credentials below, set on this module's
  own config entry.
* **Agent** — ``agents/WSRAgent.py``.
* **App** — discovered from ``apps/dashboard/manifest.json``, app id
  ``naas_abi_marketplace.domains.intelligence.modules.wsr:dashboard``.

The dashboard under ``apps/dashboard/`` stays a standalone service with its own
``pyproject.toml``, ``Dockerfile`` and ``.env``; see ``README.md``.
"""

from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[],
    )

    class Configuration(ModuleConfiguration):
        """
        module: naas_abi_marketplace.domains.intelligence.modules.wsr
        enabled: true
        config:
            opensky_client_id: ""
            opensky_client_secret: ""
            tfl_app_key: ""
            openwebcamdb_api_key: ""
            demo_login: ""
            demo_password: ""
        """

        # The dashboard backend reads these from its own environment
        # (``apps/dashboard/api/.env``); the values here are the workspace-level
        # source of truth used to provision it. Leave a key blank to disable
        # that data source — every adapter degrades gracefully.
        opensky_client_id: str = ""
        opensky_client_secret: str = ""
        tfl_app_key: str = ""
        openwebcamdb_api_key: str = ""
        demo_login: str = ""
        demo_password: str = ""
